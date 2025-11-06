from math import log10,floor
from decimal import Decimal,getcontext
from typing import Union
from array import array

getcontext().prec = 6

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


def makeListIntArray(entry_list : list):

    try:
        return array('I',entry_list)
    except Exception:
        try:
            return array('L',entry_list)
        except Exception:
            return array('Q',entry_list)

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
