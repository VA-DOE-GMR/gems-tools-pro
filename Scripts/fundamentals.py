import colorsys
from colormath.color_objects import LabColor,sRGBColor
from colormath.color_conversions import convert_color
from decimal import Decimal,getcontext
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

    initial_context = getcontext().prec
    getcontext().prec = 3
    getcontext().prec = initial_context

    num = Decimal(str(num))

    if num <= 8:
        if num < Decimal(8) - num:
            getcontext().prec = initial_context
            return '0'
        getcontext().prec = initial_context
        return 'A'
    elif num <= 13:
        if num < Decimal(13) - num:
            getcontext().prec = initial_context
            return 'A'
        getcontext().prec = initial_context
        return '1'
    elif num <= 20:
        if num < Decimal(20) - num:
            getcontext().prec = initial_context
            return '1'
        getcontext().prec = initial_context
        return '2'
    elif num <= 30:
        if num < Decimal(30) - num:
            getcontext().prec = initial_context
            return '2'
        getcontext().prec = initial_context
        return '3'
    elif num <= 40:
        if num < Decimal(40) - num:
            getcontext().prec = initial_context
            return '3'
        getcontext().prec = initial_context
        return '4'
    elif num <= 50:
        if num < Decimal(50) - num:
            getcontext().prec = initial_context
            return '4'
        getcontext().prec = initial_context
        return '5'
    elif num <= 60:
        if num < Decimal(60) - num:
            getcontext().prec = initial_context
            return '5'
        getcontext().prec = initial_context
        return '6'
    elif num <= 70:
        if num < Decimal(70) - num:
            getcontext().prec = initial_context
            return '6'
        getcontext().prec = initial_context
        return '7'
    else:
        if num < Decimal(100) - num:
            getcontext().prec = initial_context
            return '7'
        getcontext().prec = initial_context
        return 'X'

def cmy_into_wpg(cmy : tuple) -> str:

    return color_dict[f'{wpg_val(cmy[0])}{wpg_val(cmy[1])}{wpg_val(cmy[2])}']
