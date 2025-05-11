import datetime
import json
import time
import uuid
from pathlib import Path
from typing import Any

import icalendar
from fastapi import FastAPI
from fastapi.responses import FileResponse

DEFAULT_EVENT_DURATION = datetime.timedelta(minutes=20)

app = FastAPI()


def get_from_multiple_dicts(dict_list, key: str) -> Any:
    for dictionary in dict_list:
        if key in dictionary:
            return dictionary[key]
    return None


def get_timedelta_from_iso_time(iso_time: str) -> datetime.timedelta:
    negative = False
    if iso_time.startswith("-"):
        iso_time = iso_time[1:]
        negative = True
    if iso_time.startswith("+"):
        iso_time = iso_time[1:]
        negative = False
    iso_time = iso_time.strip()

    datetime_time: datetime.time = datetime.time.fromisoformat(iso_time)
    result = datetime.timedelta(
        hours=datetime_time.hour * -1 if negative else datetime_time.hour,
        minutes=datetime_time.minute * -1 if negative else datetime_time.minute,
        seconds=datetime_time.second * -1 if negative else datetime_time.second
    )

    return result


def main():
    start_time = time.time()

    calendar_main = icalendar.Calendar()
    calendar_main.add("prodid", "TraitCal Main Events")
    calendar_main.add("version", "2.0")

    calendar_events = icalendar.Calendar()
    calendar_events.add("prodid", "TraitCal Other Events")
    calendar_events.add("version", "2.0")

    tz = icalendar.Timezone.from_ical("""
BEGIN:VTIMEZONE
TZID:Asia/Tbilisi
BEGIN:STANDARD
DTSTART:20050101T000000
TZOFFSETFROM:+0300
TZOFFSETTO:+0400
TZNAME:GET
END:STANDARD
END:VTIMEZONE
""")

    calendar_main.add_component(tz)
    calendar_events.add_component(tz)

    tz_offset = datetime.timezone(datetime.timedelta(hours=4))

    with open("input/calendar.json") as f:
        calendar_data = json.load(f)

    with open("input/traits.json") as f:
        traits_data = json.load(f)

    traits_dict = {trait["name"]: trait for trait in traits_data}

    data_loaded_time = time.time()

    for day in calendar_data:
        day_date = datetime.date.fromisoformat(day.get("date"))

        print(f" * * * Day date: {day_date} * * * \n")

        for trait in day["traits"]:
            trait_name = trait["name"]

            print(f" * Trait name: {trait_name} * \n")

            trait_main_event_dict_pair = (trait.get("main_event", {}), traits_dict[trait_name].get("main_event", {}))

            trait_main_event_name = traits_dict[trait_name]["main_event"]["name"]
            trait_main_event_start_time_str = get_from_multiple_dicts(trait_main_event_dict_pair, "start_time")
            trait_main_event_duration_str = get_from_multiple_dicts(trait_main_event_dict_pair, "duration")
            trait_main_event_end_time_str = get_from_multiple_dicts(trait_main_event_dict_pair, "end_time")
            trait_main_event_description_str = get_from_multiple_dicts(trait_main_event_dict_pair, "description")
            trait_main_event_busy_bool = get_from_multiple_dicts(trait_main_event_dict_pair, "busy")

            if trait_main_event_busy_bool is None:
                trait_main_event_busy_bool = False

            trait_main_event_start_time = None
            if trait_main_event_start_time_str:
                trait_main_event_start_time = datetime.datetime.combine(
                    day_date,
                    datetime.time.fromisoformat(trait_main_event_start_time_str)
                )

            trait_main_event_duration = None
            if trait_main_event_duration_str:
                trait_main_event_duration = get_timedelta_from_iso_time(trait_main_event_duration_str)

            trait_main_event_end_time = None
            if trait_main_event_end_time_str:
                trait_main_event_end_time = datetime.datetime.combine(
                    day_date,
                    datetime.time.fromisoformat(trait_main_event_end_time_str)
                )

            trait_main_event_description = trait_main_event_description_str

            if not trait_name:
                raise ValueError("Invalid trait name")

            if not trait_main_event_name:
                raise ValueError("Invalid main event name")

            if not trait_main_event_start_time:
                raise ValueError("Invalid main event start time")

            if trait_main_event_duration:
                trait_main_event_end_time = trait_main_event_start_time + trait_main_event_duration

            if not trait_main_event_end_time:
                trait_main_event_end_time = trait_main_event_start_time + DEFAULT_EVENT_DURATION

            if trait_main_event_end_time < trait_main_event_start_time:
                trait_main_event_end_time += datetime.timedelta(days=1)

            trait_main_event_start_time = trait_main_event_start_time.astimezone(tz_offset)
            trait_main_event_end_time = trait_main_event_end_time.astimezone(tz_offset)

            print(
                f"Main event name: {trait_main_event_name}\n"
                f"Main event start time: {trait_main_event_start_time}\n"
                f"Main event duration: {trait_main_event_duration}\n"
                f"Main event end time: {trait_main_event_end_time}\n" +
                (f"Main event description: {trait_main_event_description}\n" if trait_main_event_description else "") +
                f"Main event busy: {trait_main_event_busy_bool}\n"
            )

            main_event_component = icalendar.Event()  # noqa
            main_event_component.add("uid", uuid.uuid4())
            main_event_component.add("summary", trait_main_event_name)
            main_event_component.add("dtstamp", datetime.datetime.now().astimezone(tz_offset))
            main_event_component.add("dtstart", trait_main_event_start_time)
            main_event_component.add("dtend", trait_main_event_end_time)
            if trait_main_event_description:
                main_event_component.add("description", trait_main_event_description)
            main_event_component.add("transp", "OPAQUE" if trait_main_event_busy_bool else "TRANSPARENT")
            calendar_main.add_component(main_event_component)

            if "events" not in traits_dict[trait_name]:
                continue

            for event in traits_dict[trait_name]["events"]:
                event_name = event["name"]

                event_day_delta_int = event.get("day_delta")
                event_start_time_str = event.get("start_time")
                event_start_time_delta_str = event.get("start_time_delta")
                event_start_time_delta_from_end = event.get("start_time_delta_from_end")
                event_end_time_str = event.get("end_time")
                event_end_time_delta_str = event.get("end_time_delta")
                event_end_time_delta_from_start = event.get("end_time_delta_from_start")
                event_duration_str = event.get("duration")
                event_description_str = event.get("description")
                event_busy_bool = event.get("busy", False)

                event_start_time = None
                event_end_time = None

                if event_day_delta_int:
                    event_start_day = day_date + datetime.timedelta(days=int(event_day_delta_int))
                else:
                    event_start_day = day_date
                    event_day_delta_int = 0

                if event_start_time_str:
                    event_start_time = datetime.datetime.combine(
                        event_start_day,
                        datetime.time.fromisoformat(event_start_time_str)
                    ).astimezone(tz_offset)
                elif event_start_time_delta_str:
                    if trait_main_event_start_time:
                        event_start_time = trait_main_event_start_time + get_timedelta_from_iso_time(event_start_time_delta_str) + datetime.timedelta(days=int(event_day_delta_int))
                elif event_start_time_delta_from_end:
                    if trait_main_event_end_time:
                        event_start_time = trait_main_event_end_time + get_timedelta_from_iso_time(event_start_time_delta_from_end) + datetime.timedelta(days=int(event_day_delta_int))

                if not event_start_time:
                    raise ValueError(f"Could not determine start time for event '{event_name}'")

                event_start_time = event_start_time.astimezone(tz_offset)

                if event_end_time_str:
                    event_end_time = datetime.datetime.combine(
                        event_start_day,
                        datetime.time.fromisoformat(event_end_time_str)
                    )
                elif event_end_time_delta_str:
                    if trait_main_event_start_time:
                        event_end_time = trait_main_event_end_time + get_timedelta_from_iso_time(event_end_time_delta_str) + datetime.timedelta(days=int(event_day_delta_int))
                elif event_end_time_delta_from_start:
                    event_end_time = trait_main_event_start_time + get_timedelta_from_iso_time(event_end_time_delta_from_start)
                elif event_duration_str:
                    event_end_time = event_start_time + get_timedelta_from_iso_time(event_duration_str)

                if not event_end_time:
                    event_end_time = event_start_time + DEFAULT_EVENT_DURATION

                event_end_time = event_end_time.astimezone(tz_offset)

                if event_end_time < event_start_time:
                    event_end_time += datetime.timedelta(days=1)

                print(f"Event name: {event_name}\n"
                      f"Event start time: {event_start_time}\n"
                      f"Event end time: {event_end_time}\n" +
                      (f"Event description: {event_description_str}\n" if event_description_str else "") +
                      f"Event busy: {event_busy_bool}\n")

                event_component = icalendar.Event()  # noqa
                event_component.add("uid", uuid.uuid4())
                event_component.add("summary", event_name)
                event_component.add("dtstamp", datetime.datetime.now().astimezone(tz_offset))
                event_component.add("dtstart", event_start_time)
                event_component.add("dtend", event_end_time)
                if event_description_str:
                    event_component.add("description", event_description_str)
                event_component.add("transp", "OPAQUE" if event_busy_bool else "TRANSPARENT")

                calendar_events.add_component(event_component)

    data_processed_time = time.time()

    ical_main = calendar_main.to_ical()
    ical_events = calendar_events.to_ical()

    with open("output/main.ics", "wb") as f:
        f.write(ical_main)

    with open("output/other.ics", "wb") as f:
        f.write(ical_events)

    print(ical_main.decode("utf-8"))

    print(ical_events.decode("utf-8"))

    finish_time = time.time()

    print(f"Data loaded in {data_loaded_time - start_time:.6f} seconds")
    print(f"Data processed in {data_processed_time - data_loaded_time:.6f} seconds")
    print(f"Data saved to iCal and written to file in {finish_time - data_processed_time:.6f} seconds")
    print(f"Total time: {finish_time - start_time:.6f} seconds")
    return


if __name__ == '__main__':
    main()


@app.get("/main.ics", response_class=FileResponse)
def get_calendar_main():
    return FileResponse(
        path=Path("output/main.ics"),
        media_type="text/calendar; charset=utf-8",
        filename="main.ics"
    )


@app.get("/other.ics", response_class=FileResponse)
def get_calendar_other():
    return FileResponse(
        path=Path("output/other.ics"),
        media_type="text/calendar; charset=utf-8",
        filename="other.ics"
    )


@app.post("/update_traits")
def update_traits(data: list[dict[str, Any]]):
    with open("input/traits.json", "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    main()
    try:
        main()
    except Exception as e:
        return {"message": f"Error occurred while updating traits: {e}"}
    return {"message": "Traits updated"}


@app.post("/update_calendar")
def update_calendar(data: list[dict[str, Any]]):
    with open("input/calendar.json", "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    try:
        main()
    except Exception as e:
        return {"message": f"Error occurred while updating calendar: {e}"}
    return {"message": "Calendar updated"}
