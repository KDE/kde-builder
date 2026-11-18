# SPDX-FileCopyrightText: 2026 Christoph Martin <foss@c14n.ch>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from typing import Any


class Forceable[T]:
    """A setting that can be forced or set regularly."""

    def __init__(self, value: T, *, forced: bool = False):
        self._value = value
        self._forced = forced

    @property
    def forced(self) -> bool:
        return self._forced

    @property
    def value(self) -> T:
        return self._value

    @value.setter
    def value(self, value: T) -> None:
        self.set(value)

    def set(self, value: T, *, force: bool = False) -> bool:
        """
        Set the value.

        Args:
            value:
                The new setting value.
            force:
                Whether to force the setting.

                If force is True, the new value is always set.

                If force is False, the new value is only applied if the setting
                was not forced previously.

        Returns:
            Whether the value was changed.
        """
        if self._forced and not force:
            return False

        self._forced = force

        if self._value == value:
            return False

        self._value = value

        return True


class ForceableBool(Forceable[bool]):
    """A boolean setting that can be forced or set regularly."""

    def __init__(self, name: str, value: bool, *, forced: bool = False):
        self._name = name

        super().__init__(value, forced=forced)

    def set_checked(self, value: Any, *, force: bool = False) -> bool:
        """
        Set the value.

        Args:
            value:
                The new setting value.
            force:
                Whether to force the setting.

                If force is True, the new value is always set.

                If force is False, the new value is only applied if the setting
                was not forced previously.

        Returns:
            Whether the value was changed.

        Raises:
            TypeError: If value is not a boolean.
        """
        if not isinstance(value, bool):
            raise TypeError(f"Cannot use {type(value)} as {self._name}: needs boolean.")

        return self.set(value, force=force)
