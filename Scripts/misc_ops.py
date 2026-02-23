from array import array

class Referential_Information:

    def __init__(self):
        """
        This is for filling out _ID ending fields in feature classes.
        """

        self.idRootDict = {"CartographicLines": "CAL","ContactsAndFaults":"CAF","CMULines":"CMULIN","CMUMapUnitPolys":"CMUMUP","CMUPoints":"CMUPNT","CMUText":"CMUTXT","DataSources":"DAS","DataSourcePolys":"DSP","DescriptionOfMapUnits":"DMU","ExtendedAttributes":"EXA","FossilPoints":"FSP","GenericPoints":"GNP","GenericSamples":"GNS","GeochemPoints":"GCM","GeochronPoints":"GCR","GeologicEvents":"GEE","GeologicLines":"GEL","Glossary":"GLO","IsoValueLines":"IVL","MapUnitPoints":"MPT","MapUnitPolys":"MUP","MapUnitOverlayPolys":"MUO","MiscellaneousMapInformation":"MMI","OrientationPoints":"ORP","OtherLines":"OTL","OverlayPolys":"OVP","PhotoPoints":"PHP","RepurposedSymbols":"RPS","Stations":"STA","StandardLithology":"STL","MapUnitPointAnno24k":"ANO"}
        self.x_id_count = 0

    def getRootName(self, fc_name : str) -> str:
        """
        This determines the prefix used for _ID ending fields in feature classes.
        """

        if fc_name.startswith("CS"):
            prefix = 'CS'
            fc_name = fc_name[2:]
            while fc_name[:2].isupper():
                prefix = f'{prefix}{fc_name[0]}'
                fc_name = fc_name[:1]
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
