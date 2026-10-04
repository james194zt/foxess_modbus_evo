"""FoxESS EVO Mode Scheduler register layout (see docs/evo/mode-scheduler.md).

Pure encode/decode/validation, with no Home Assistant or Modbus dependencies.
"""

from dataclasses import dataclass
from dataclasses import replace
from datetime import time

SCHEDULER_ENABLE_ADDRESS = 48000
GROUP_BASE_ADDRESS = 48010
GROUP_SIZE = 10
# The Fox app manages groups 1-8 and rewrites all of them on every save
MANAGED_GROUP_COUNT = 8
# The last managed group holds the "Remaining Time Slots" filler, as the Fox app does
MAX_USER_GROUPS = MANAGED_GROUP_COUNT - 1

# 1-based codes, shared with work mode register 49203
WORK_MODE_CODES = {
    "self_use": 1,
    "feed_in": 2,
    "back_up": 3,
    "force_charge": 6,
    "force_discharge": 7,
}
WORK_MODE_NAMES = {code: name for name, code in WORK_MODE_CODES.items()}

# Offset +8, as written by the Fox app for a freshly created slot of each mode. Unverified meaning
# (probably bit 0 = PV, bit 1 = grid). Back-up was only seen carrying over a previous value of 3.
_DEFAULT_FLAGS = {
    "self_use": 0,
    "feed_in": 1,
    "back_up": 3,
    "force_charge": 3,
    "force_discharge": 3,
}

# Ranges reported by Fox Cloud for the EVO 10-5-H scheduler
MIN_SOC_RANGE = (5, 100)
MAX_SOC_RANGE = (10, 100)
FD_SOC_RANGE = (5, 100)
FD_PWR_RANGE = (0, 12000)

# Offset +9 on groups the Fox app manages
_MANAGED_SLOT_MARKER = 1


class ScheduleError(ValueError):
    """A schedule that can't be written to the inverter."""


def group_address(index: int) -> int:
    """Start address of group `index` (0-based)."""
    return GROUP_BASE_ADDRESS + GROUP_SIZE * index


def _encode_time(value: time) -> int:
    return (value.hour << 8) | value.minute


def _decode_time(value: int) -> time:
    hour, minute = value >> 8, value & 0xFF
    if hour > 23 or minute > 59:
        raise ScheduleError(f"Invalid time register value {value}")
    return time(hour=hour, minute=minute)


@dataclass(frozen=True)
class ScheduleGroup:
    """One 10-register time group."""

    enabled: bool
    start: time
    end: time
    work_mode: int
    min_soc: int = 10
    max_soc: int = 100
    fd_soc: int = 10
    fd_pwr: int = 0
    # Offsets +7, +8 and +9: meaning unverified, so carried as raw values
    reserved: int = 0
    flags: int = 0
    slot_marker: int = _MANAGED_SLOT_MARKER

    def to_registers(self) -> list[int]:
        return [
            1 if self.enabled else 0,
            _encode_time(self.start),
            _encode_time(self.end),
            self.work_mode,
            (self.max_soc << 8) | self.min_soc,
            self.fd_soc,
            self.fd_pwr,
            self.reserved,
            self.flags,
            self.slot_marker,
        ]

    @classmethod
    def from_registers(cls, registers: list[int]) -> "ScheduleGroup":
        if len(registers) != GROUP_SIZE:
            raise ScheduleError(f"A group is {GROUP_SIZE} registers, got {len(registers)}")
        return cls(
            enabled=registers[0] != 0,
            start=_decode_time(registers[1]),
            end=_decode_time(registers[2]),
            work_mode=registers[3],
            max_soc=registers[4] >> 8,
            min_soc=registers[4] & 0xFF,
            fd_soc=registers[5],
            fd_pwr=registers[6],
            reserved=registers[7],
            flags=registers[8],
            slot_marker=registers[9],
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "start": self.start.strftime("%H:%M"),
            "end": self.end.strftime("%H:%M"),
            "work_mode": WORK_MODE_NAMES.get(self.work_mode, self.work_mode),
            "min_soc": self.min_soc,
            "max_soc": self.max_soc,
            "fd_soc": self.fd_soc,
            "fd_pwr": self.fd_pwr,
            "raw_reserved": self.reserved,
            "raw_flags": self.flags,
            "raw_slot_marker": self.slot_marker,
        }


# What the Fox app writes into an unused slot
BLANK_GROUP = ScheduleGroup(enabled=False, start=time(0, 0), end=time(0, 0), work_mode=WORK_MODE_CODES["self_use"])


def _check_range(name: str, value: int, value_range: tuple[int, int]) -> None:
    low, high = value_range
    if not low <= value <= high:
        raise ScheduleError(f"{name} must be between {low} and {high}, got {value}")


def make_group(
    *,
    start: time,
    end: time,
    work_mode: str,
    min_soc: int = 10,
    max_soc: int = 100,
    fd_soc: int = 10,
    fd_pwr: int = 0,
) -> ScheduleGroup:
    """Build an enabled group the way the Fox app would, validating every field."""
    if work_mode not in WORK_MODE_CODES:
        raise ScheduleError(f"Unknown work mode '{work_mode}'. Valid: {', '.join(WORK_MODE_CODES)}")
    if start.second or end.second:
        raise ScheduleError("Start and end times must be whole minutes")
    if end <= start:
        raise ScheduleError(
            f"End {end:%H:%M} must be after start {start:%H:%M}; split slots that cross midnight in two"
        )
    _check_range("min_soc", min_soc, MIN_SOC_RANGE)
    _check_range("max_soc", max_soc, MAX_SOC_RANGE)
    _check_range("fd_soc", fd_soc, FD_SOC_RANGE)
    _check_range("fd_pwr", fd_pwr, FD_PWR_RANGE)
    if min_soc > max_soc:
        raise ScheduleError(f"min_soc ({min_soc}) must not be above max_soc ({max_soc})")
    return ScheduleGroup(
        enabled=True,
        start=start,
        end=end,
        work_mode=WORK_MODE_CODES[work_mode],
        min_soc=min_soc,
        max_soc=max_soc,
        fd_soc=fd_soc,
        fd_pwr=fd_pwr,
        flags=_DEFAULT_FLAGS[work_mode],
    )


def build_managed_groups(groups: list[ScheduleGroup], remaining: ScheduleGroup) -> list[ScheduleGroup]:
    """Lay out all managed slots: the user's groups, the all-day filler, then blank slots.

    The filler goes after the user's groups because earlier slots take priority where they overlap.
    """
    if len(groups) > MAX_USER_GROUPS:
        raise ScheduleError(f"At most {MAX_USER_GROUPS} slots are supported, got {len(groups)}")
    filler = replace(remaining, start=time(0, 0), end=time(23, 59))
    managed = [*groups, filler]
    return managed + [BLANK_GROUP] * (MANAGED_GROUP_COUNT - len(managed))


def decode_groups(registers: list[int]) -> list[ScheduleGroup]:
    """Decode consecutive groups starting at GROUP_BASE_ADDRESS."""
    if len(registers) % GROUP_SIZE:
        raise ScheduleError(f"Register count {len(registers)} is not a whole number of groups")
    return [ScheduleGroup.from_registers(registers[i : i + GROUP_SIZE]) for i in range(0, len(registers), GROUP_SIZE)]
