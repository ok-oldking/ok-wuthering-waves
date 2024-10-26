from enum import Enum

class Echos(Enum):
    DEFAULT8 =              (8, 0)
    DEFAULT15 =             (15,0)
    DEFAULT20 =             (20,0)
    BELL_BORNE_GEOCHELONE = (20, 0)
    CROWNLESS =             (20, 2.5)#not checked
    THUNDERING_MEPHIS =     (20, 2.2)#not checked
    TEMPEST_MEPHIS =        (20, 1)#not checked
    INFERNO_RIDER =         (20, 1.6)
    FEILIAN_BERINGAL =      (20, 0.7)#not checked
    MOURNING_AIX =          (20, 1)#not checked
    IMPERMANENCE_HERON =    (20, 0)
    LAMPYLUMEN_MYRIAD =     (20, 2.5)#not checked
    MECH_ABOMINATION =      (20, 0)
    FALLACY_OF_NO_RETURN =  (20, 0)
    JUE =                   (20, 0)
    DREAMLESS =             (20, 0)

    @property
    def echo_cd(self):
        return self.value[0]
    @property
    def echo_animation_duration(self):
        return self.value[1]