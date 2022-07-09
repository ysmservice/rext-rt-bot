# RT - Converters

from typing import NoReturn

from datetime import datetime, timedelta

from discord.ext import commands


__all__ = (
    "BaseDateTimeConverter", "TimeConverter", "DayOfWeekConverter",
    "DateConverter", "DayOfWeekTimeConverter", "DateDayOfWeekConverter",
    "DateTimeConverter", "DateDayOfWeekTimeConverter",
    "DateTimeFormatNotSatisfiable"
)


class DateTimeFormatNotSatisfiable(commands.BadArgument):
    "Occurs when `BaseDateTimeConverter`'s convert fails."

    def __init__(self, arg: str):
        super().__init__(f"{arg!r} is not properly formatted.")
class BaseDateTimeConverter(commands.Converter[datetime]):
    "Time converter. Precisely the converter that should be used is a class that extends this class."

    FORMAT: str

    @staticmethod
    def raise_(arg: str) -> NoReturn:
        raise DateTimeFormatNotSatisfiable(arg)

    async def convert(self, _: commands.Context, arg: str) -> datetime:
        dt = datetime.now().strptime(arg, self.FORMAT)
        # もし昔の月の場合は来年の年を書き込む。それ以外は今年を書き込む。
        now = datetime.now()
        dt = dt.replace(year=(now.year + 1) if dt < now else now.year)
        try:
            return dt
        except ValueError:
            self.raise_(arg)
class TimeConverter(BaseDateTimeConverter):
    FORMAT = "%H:%M"
class DayOfWeekConverter(BaseDateTimeConverter):
    FORMAT = "%a"
class DateConverter(BaseDateTimeConverter):
    FORMAT = "%m-%d"
class DayOfWeekTimeConverter(BaseDateTimeConverter):
    FORMAT = f"{DayOfWeekConverter.FORMAT},{TimeConverter.FORMAT}"
class DateDayOfWeekConverter(BaseDateTimeConverter):
    FORMAT = f"{DateConverter.FORMAT},{DayOfWeekConverter.FORMAT}"
class DateTimeConverter(BaseDateTimeConverter):
    FORMAT = f"{DateConverter.FORMAT},{TimeConverter.FORMAT}"
class DateDayOfWeekTimeConverter(BaseDateTimeConverter):
    FORMAT = DateTimeConverter.FORMAT.replace(",", f",{DayOfWeekConverter.FORMAT},")