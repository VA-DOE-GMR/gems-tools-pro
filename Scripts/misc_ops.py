from array import array
from typing import Union

class Referential_Information:

    def __init__(self):
        """
        This is for filling out _ID ending fields in feature classes.
        """

        self.idRootDict = {"CartographicLines": "CAL","ContactsAndFaults":"CAF","CMULines":"CMULIN","CMUMapUnitPolys":"CMUMUP","CMUPoints":"CMUPNT","CMUText":"CMUTXT","DataSources":"DAS","DataSourcePolys":"DSP","DescriptionOfMapUnits":"DMU","ExtendedAttributes":"EXA","FossilPoints":"FSP","GenericPoints":"GNP","GenericSamples":"GNS","GeochemPoints":"GCM","GeochronPoints":"GCR","GeologicEvents":"GEE","GeologicLines":"GEL","Glossary":"GLO","IsoValueLines":"IVL","MapUnitPoints":"MPT","MapUnitPolys":"MUP","MapUnitOverlayPolys":"MUO","MiscellaneousMapInformation":"MMI","OrientationPoints":"ORP","OtherLines":"OTL","OverlayPolys":"OVP","PhotoPoints":"PHP","RepurposedSymbols":"RPS","Stations":"STA","StandardLithology":"STL","MapUnitPointAnno24k":"ANO"}
        self.x_id_count = 0
        self.annotation_items = set() # must be manually defined.

    def getRootName(self, fc_name : str) -> str:
        """
        This determines the prefix used for _ID ending fields in feature classes.
        """

        if fc_name.startswith("CS"):
            prefix = 'CS'
            fc_name = fc_name[2:]
            while fc_name[:2].isupper():
                prefix = f'{prefix}{fc_name[0]}'
                fc_name = fc_name[1:]
            if fc_name in self.idRootDict.keys():
                return f'{prefix}{self.idRootDict[fc_name]}'
            else:
                self.x_id_count += 1
                return f'{prefix}X{self.x_id_count}X'
        else:
            if fc_name in self.idRootDict.keys():
                return self.idRootDict[fc_name]
            else:
                self.x_id_count += 1
                return f'X{self.x_id_count}X'


ref_info = Referential_Information()


def makeListIntArray(entry_list : list) -> array:

    try:
        return array('I',entry_list)
    except Exception:
        try:
            return array('L',entry_list)
        except Exception:
            return array('Q',entry_list)


def getOIDSelectionStr(oids : Union[tuple,list,array], oid_name : str) -> Union[None,str]:
    if len(oids) >= 2:
        if not isinstance(oids[0],str):
            oids = tuple([str(oid) for oid in oids])
        return f'{oid_name} IN ({",".join(oids)})'
    elif len(oids) == 1:
        if not isinstance(oids[0],str):
            oids[0] = str(oids[0])
        return f'{oid_name} = {oids[0]}'
    else:
        return None
