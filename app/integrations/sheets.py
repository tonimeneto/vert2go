"""Read only the declared spreadsheet and exact finite ranges."""
from app.core.contracts import EngineError
from app.integrations.google_config import a1_range


class Sheets:
    def __init__(self, config, http):
        self.config, self.http = config, http

    def write_row(self, spreadsheet_id, target, values):
        return self.http.row_request(spreadsheet_id,target,values)

    def read_metadata(self, spreadsheet_id):
        value = self.http.read('sheets.metadata', spreadsheet_id).json()
        if value.get('spreadsheetId') != spreadsheet_id or type(value.get('properties', {})) is not dict:
            raise EngineError('google_response_invalid')
        return value

    def read_structure(self, spreadsheet_id):
        """Only explicitly authorized tab names/dimensions. No cells or used-range inference."""
        value = self.http.read('sheets.structure', spreadsheet_id).json()
        if value.get('spreadsheetId') != spreadsheet_id or type(value.get('sheets')) is not list:
            raise EngineError('google_response_invalid')
        result = []
        for sheet in value['sheets']:
            props = sheet.get('properties') if type(sheet) is dict else None
            if type(props) is not dict or type(props.get('sheetId')) is not int or type(props.get('title')) is not str or not 1 <= len(props['title']) <= 100:
                raise EngineError('google_response_invalid')
            entry = {k: props[k] for k in ('sheetId','title','sheetType') if k in props}
            grid = props.get('gridProperties')
            if grid is not None:
                if type(grid) is not dict or any(type(grid.get(k)) is not int or grid[k] < 1 for k in ('rowCount','columnCount')):
                    raise EngineError('google_response_invalid')
                entry['gridProperties'] = {k: grid[k] for k in ('rowCount','columnCount')}
            result.append(entry)
        named_ranges = value.get('namedRanges', [])
        if type(named_ranges) is not list:
            raise EngineError('google_response_invalid')
        names = []
        for item in named_ranges:
            if type(item) is not dict or type(item.get('name')) is not str or type(item.get('range')) is not dict:
                raise EngineError('google_response_invalid')
            bounds = item['range']
            if any(type(v) is not int or v < 0 for v in bounds.values()):
                raise EngineError('google_response_invalid')
            names.append({'name': item['name'], 'range': {k: bounds[k] for k in
                          ('sheetId','startRowIndex','endRowIndex','startColumnIndex','endColumnIndex') if k in bounds}})
        return {'tabs': result, 'named_ranges': names}

    def read_range(self, spreadsheet_id, target):
        value = self.http.read('sheets.values', spreadsheet_id, range=target).json()
        rows = value.get('values', [])
        if type(rows) is not list or any(type(row) is not list for row in rows):
            raise EngineError('google_response_invalid')
        if sum(len(row) for row in rows) > min(a1_range(target), self.config.max_cells):
            raise EngineError('google_response_limit')
        import re
        bounds = re.search(r'!([A-Z]+)([0-9]+):([A-Z]+)([0-9]+)$', target)
        def column(text):
            result=0
            for char in text: result=result*26+ord(char)-64
            return result
        if len(rows) > int(bounds[4])-int(bounds[2])+1 or any(len(row)>column(bounds[3])-column(bounds[1])+1 for row in rows):
            raise EngineError('google_response_limit')
        if any(type(cell) not in (str, int, float, bool) for row in rows for cell in row):
            raise EngineError('google_response_invalid')
        return rows
