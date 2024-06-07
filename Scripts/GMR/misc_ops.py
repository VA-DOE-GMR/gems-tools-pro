from string import punctuation,ascii_letters,digits
from math import log10,floor
from array import array
from decimal import Decimal,getcontext
from color_code_dict import color_dict

getcontext().prec = 6

alphanum = frozenset(list(f'{digits}{ascii_letters}'))
double_puncts = tuple([punct * 2 for punct in array('u',list(punctuation))])

class Referential_Information:

    def __init__(self):
        """
        This is for filling out _ID ending fields in feature classes.
        """

        self.idRootDict = {"CartographicLines": "CAL","ContactsAndFaults":"CAF","CMULines":"CMULIN","CMUMapUnitPolys":"CMUMUP","CMUPoints":"CMUPNT","CMUText":"CMUTXT","DataSources":"DAS","DataSourcePolys":"DSP","DescriptionOfMapUnits":"DMU","ExtendedAttributes":"EXA","FossilPoints":"FSP","GenericPoints":"GNP","GenericSamples":"GNS","GeochemPoints":"GCM","GeochronPoints":"GCR","GeologicEvents":"GEE","GeologicLines":"GEL","Glossary":"GLO","IsoValueLines":"IVL","MapUnitPoints":"MPT","MapUnitPolys":"MUP","MapUnitOverlayPolys":"MUO","MiscellaneousMapInformation":"MMI","OrientationPoints":"ORP","OtherLines":"OTL","OverlayPolys":"OVP","PhotoPoints":"PHP","RepurposedSymbols":"RPS","Stations":"STA","StandardLithology":"STL","MapUnitPointAnno24k":"ANO"}
        self.x_id_count = 0

    def getRootName(self,fc_name) -> str:
        """
        This determines the prefix used for _ID ending fields in feature classes.
        """

        if fc_name.startswith("CS"):
            if fc_name[3:] in self.idRootDict.keys():
                return f'{fc_name[:3]}{self.idRootDict[fc_name[3:]]}'
            else:
                self.x_id_count += 1
                return f'{fc_name[:3]}X{self.x_id_count}X'
        else:
            if fc_name in self.idRootDict.keys():
                return self.idRootDict[fc_name]
            else:
                self.x_id_count += 1
                return f'X{self.x_id_count}X'

ref_info = Referential_Information()

def to_tuple(lst : list) -> tuple:
    '''Converts nested list into nested tuple
    Nested tuples are excellent for reducing memory-usage
    as well as efficiency of loops using the outputed
    nested tuple.'''

    # works with non-nested lists as well.

    return tuple(to_tuple(i) if isinstance(i,list) else i for i in lst)

def to_list(tple : tuple) -> list:
    '''Converts nested tuple into nested list.
    This mainly exists with the idea of modifying items in a nested tuple
    before converting it back into a nested tuple via to_tuple.'''

    # works with non-nested tuples as well.

    return list(to_list(i) if isinstance(i,tuple) else i for i in tple)

# returning None indicates that is nothing of importance in that string.
def fixFieldItemString(entry_string : str):
    # No String entry should have consecutive spaces.
    while entry_string.find('  ') != -1:
        entry_string = entry_string.replace('  ',' ')
    # No String entry should be begin and/or end with a space.
    entry_string = entry_string.strip()
    # No String entry should have two or more consecutive punctuation characters.
    if entry_string == '':
        return None
    for double_punct in double_puncts:
        if double_punct in entry_string:
            while double_punct in entry_string:
                entry_string = entry_string.replace(double_punct,double_punct[0])
    for item in entry_string:
        if item in alphanum:
            return entry_string

    return None

def rgb_to_fgdc(rgb_vals) -> str:
    '''Values in tuple/list/array can only be whole numbers
    between 0 and 255.
    '''

    fgdc = ''

    for n in range(len(rgb_vals)):
        # Convert into percentage values.
        temp_val = Decimal(rgb_vals[n]) / Decimal(255) * Decimal(100)
        if temp_val <= 8:
            if Decimal(8) - temp_val <= temp_val:
                fgdc = f'{fgdc}A'
            else:
                fgdc = f'{fgdc}0'
        elif temp_val > 8 and temp_val <= 13:
            if Decimal(13) - temp_val <= Decimal(8) - temp_val:
                fgdc = f'{fgdc}1'
            else:
                fgdc = f'{fgdc}A'
        elif temp_val > 13 and temp_val <= 20:
            if Decimal(20) - temp_val <= Decimal(13) - temp_val:
                fgdc = f'{fgdc}2'
            else:
                fgdc = f'{fgdc}1'
        elif temp_val > 20 and temp_val <= 30:
            if Decimal(30) - temp_val <= Decimal(20) - temp_val:
                fgdc = f'{fgdc}3'
            else:
                fgdc = f'{fgdc}2'
        elif temp_val > 30 and temp_val <= 40:
            if Decimal(40) - temp_val <= Decimal(30) - temp_val:
                fgdc = f'{fgdc}4'
            else:
                fgdc = f'{fgdc}3'
        elif temp_val > 40 and temp_val <= 50:
            if Decimal(13) - temp_val <= Decimal(8) - temp_val:
                fgdc = f'{fgdc}5'
            else:
                fgdc = f'{fgdc}4'
        elif temp_val > 50 and temp_val <= 60:
            if Decimal(60) - temp_val <= Decimal(50) - temp_val:
                fgdc = f'{fgdc}6'
            else:
                fgdc = f'{fgdc}5'
        elif temp_val > 60 and temp_val <= 70:
            if Decimal(70) - temp_val <= Decimal(60) - temp_val:
                fgdc = f'{fgdc}7'
            else:
                fgdc = f'{fgdc}6'
        else:
            if Decimal(100) - temp_val <= Decimal(70) - temp_val:
                fgdc = f'{fgdc}X'
            else:
                fgdc = f'{fgdc}7'

    return color_dict[fgdc]
