import pandas
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

# Export DMU to workbook
# arcpy Table to Excel?

# Load Workbook
wb = Workbook()
ws = wb.active

# Apply styles based on ParagraphStyles

styles = {
    "Unit Name": {
        "font": Font(name='Times New Roman',size='10'),
        "alignment": Alignment(horizontal='left', vertical='center')
    },
    "Unit Label": {
        "font": Font(name='FGDCGeoAge',size='10'),
        "alignment": Alignment(horizontal='center', vertical='center'),
        "border": Border(left=Side(style='thin'), right=Side(style='thin'),
                         top=Side(style='thin'), bottom=Side(style='thin'))
    },
    "Heading": {}
}