import colorsys
from colormath.color_objects import LabColor,sRGBColor
from colormath.color_conversions import convert_color
from decimal import Decimal,localcontext
from color_code_dict import color_dict

## COLOR CONVERSIONS

def hsv_into_rgb(h,s,v) -> tuple:

    rgb_vals = colorsys.hsv_to_rgb(h/360,s/100,v/100)

    return (round(rgb_vals[0]*255,0),round(rgb_vals[1]*255,0),round(rgb_vals[2]*255,0))

def hsl_into_rgb(h,s,l) -> tuple:

    rgb_vals = colorsys.hsl_to_rgb(Decimal(str(h))/360,s/100,l/100)

    return (round(rgb_vals[0]*255,0),round(rgb_vals[1]*255,0),round(rgb_vals[2]*255,0))

def lab_into_rgb(l : int, a : int, b : int) -> tuple:

    lab = LabColor(l,a,b)
    # d50 allows for best match.
    rgb = convert_color(lab,sRGBColor,target_illuminant='d50')

    return (round(rgb.rgb_r*255),round(rgb.rgb_g*255),round(rgb.rgb_b*255))

def cmy_into_rgb(c,m,y) -> tuple:

    return (round(255*(1-c/100)),round(255*(1-m/100)),round(255*(1-y/100)))

def rgb_into_cmy(r : int, g : int, b : int) -> tuple:

    return ((1-r/255)*100,(1-g/255)*100,(1-b/255)*100)

def wpg_val(num) -> str:

    with localcontext() as ctx:
        ctx.prec = 3
        num = Decimal(str(num))
        if num <= Decimal(8):
            if Decimal(8) - num >= num:
                return 'A'
            return '0'
        elif num <= Decimal(13):
            if num - Decimal(8) >= Decimal(13) - num:
                return '1'
            return 'A'
        elif num <= Decimal(20):
            if num - Decimal(13) >= Decimal(20) - num:
                return '2'
            return '1'
        elif num <= Decimal(30):
            if num - Decimal(20) >= Decimal(30) - num:
                return '3'
            return '2'
        elif num <= Decimal(40):
            if num - Decimal(30) >= Decimal(40) - num:
                return '4'
            return '3'
        elif num <= Decimal(50):
            if num - Decimal(40) >= Decimal(50) - num:
                return '5'
            return '4'
        elif num <= Decimal(60):
            if num - Decimal(50) >= Decimal(60) - num:
                return '6'
            return '5'
        elif num <= Decimal(70):
            if num - Decimal(60) >= Decimal(70) - num:
                return '7'
            return '6'
        elif num - Decimal(70) >= Decimal(100) - num:
            return 'X'
        else:
            return '7'


def cmy_into_wpg(cmy : tuple) -> str:

    return color_dict[f'{wpg_val(cmy[0])}{wpg_val(cmy[1])}{wpg_val(cmy[2])}']
