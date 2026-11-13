"""Bounded event reads. No booking, mutation, or availability decisions in I3."""
from app.core.contracts import EngineError


class Calendar:
    def __init__(self, config, http):
        self.config, self.http = config, http

    def get_event(self, calendar_id, event_id):
        return self.http.event_request('GET',calendar_id,event_id=event_id)

    def create_event(self, calendar_id, event):
        return self.http.event_request('POST',calendar_id,event=event)

    def read_events(self, calendar_id, start, end):
        events, seen, event_ids, token = [], set(), set(), None
        for _ in range(self.config.max_pages):
            arguments = {'start': start, 'end': end}
            if token is not None:
                arguments['page_token'] = token
            page = self.http.read('calendar.events', calendar_id, **arguments).json()
            if page.get('accessRole') not in ('reader','writer','owner','writerWithoutPrivateAccess') or type(page.get('items', [])) is not list:
                raise EngineError('google_calendar_access_insufficient')
            for event in page.get('items', []):
                if type(event) is not dict or type(event.get('id')) is not str or type(event.get('start')) is not dict or type(event.get('end')) is not dict:
                    raise EngineError('google_response_invalid')
                if event['id'] in event_ids:
                    raise EngineError('google_calendar_changed_during_read')
                event_ids.add(event['id'])
                events.append({key: event[key] for key in ('id','status','start','end','transparency','updated','etag') if key in event})
            token = page.get('nextPageToken')
            if token is None:
                return {'events': events, 'time_zone': page.get('timeZone'), 'complete': True}
            if type(token) is not str or not token or token in seen:
                raise EngineError('google_pagination_invalid')
            seen.add(token)
        raise EngineError('google_pagination_limit')
