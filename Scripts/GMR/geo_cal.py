# A Python3 program to find if 2 given finite line segments intersect or not

from decimal import Decimal,localcontext

class Coord_Pnt:
    def __init__(self,x,y):
        self.x = x
        self.y = y

class Line_Info:

    def __init__(self, pnt1 : Coord_Pnt, pnt2 : Coord_Pnt):

        with localcontext() as ctx:
            ctx.prec = 8
            self.m = (Decimal(str(pnt2.y))-Decimal(str(pnt1.y))) / (Decimal(str(pnt2.x))-Decimal(str(pnt1.x)))
            self.b = float(Decimal(str(pn1.y)) - self.m * Decimal(str(pn1.x)))
            self.m = float(self.m)
            self.max_x = max((x_vals := (pnt1.x,pnt2.x)))
            self.min_x = min(x_vals)
            self.max_y = max((y_vals := (pnt1.y,pnt2.y)))
            self.min_y = min(y_vals)

# Given three collinear points p, q, r, the function checks if
# point q lies on line segment 'pr'
def onSegment(p, q, r) -> bool:
    if ((q.x <= max(p.x, r.x)) and (q.x >= min(p.x, r.x)) and (q.y <= max(p.y, r.y)) and (q.y >= min(p.y, r.y))):
        return True
    return False

def orientation(p, q, r) -> int:
    # to find the orientation of an ordered triplet (p,q,r)
    # function returns the following values:
    # 0 : Collinear points
    # 1 : Clockwise points
    # 2 : Counterclockwise

    # This is to prevent interference with other modules that utilize the
    # decimal module.

    # Mitigates inaccurcies caused by floating point values used in any mathematics.
    with localcontext() as ctx:
        ctx.prec = 8
        p_x = Decimal(str(p.x))
        p_y = Decimal(str(p.y))
        q_x = Decimal(str(q.x))
        q_y = Decimal(str(q.y))
        r_x = Decimal(str(r.x))
        r_y = Decimal(str(r.y))

        if ((val := (float(q_y - p_y) * float(r_x - q_x)) - (float(q_x - p_x) * float(r_y - q_y))) > 0):
            # Clockwise orientation
            return 1
        elif (val < 0):
            # Counterclockwise orientation
            return 2
        else:
            # Collinear orientation
            return 0

# The main function that returns true if
# the line segment 'p1q1' and 'p2q2' intersect.
def doIntersect(p1,q1,p2,q2) -> bool:
    # Find the 4 orientations required for the general and special cases
    o1 = orientation(p1, q1, p2)
    o2 = orientation(p1, q1, q2)
    o3 = orientation(p2, q2, p1)
    o4 = orientation(p2, q2, q1)
    # General case
    if ((o1 != o2) and (o3 != o4)):
        return True
    # Special Cases
    # p1 , q1 and p2 are collinear and p2 lies on segment p1q1
    if ((o1 == 0) and onSegment(p1, p2, q1)):
        return True
    # p1 , q1 and q2 are collinear and q2 lies on segment p1q1
    if ((o2 == 0) and onSegment(p1, q2, q1)):
        return True
    # p2 , q2 and p1 are collinear and p1 lies on segment p2q2
    if ((o3 == 0) and onSegment(p2, p1, q2)):
        return True
    # p2 , q2 and q1 are collinear and q1 lies on segment p2q2
    if ((o4 == 0) and onSegment(p2, q1, q2)):
        return True
    # If none of the cases
    return False

def getIntersectPnt(line1 : tuple, line2 : tuple) -> Coord_Pnt:

    info_1 = Line_Info(line1[0],line1[1])
    info_2 = Line_Info(line2[0],line2[1])

    with localcontext() as ctx:
        ctx.prec = 8
        x = (Decimal(str(info_2.b)) - Decimal(str(info_1.b))) / (Decimal(str(info_1.m)) - Decimal(str(info_2.m)))
        y = float(Decimal(str(info_1.m)) * line1[0].x + Decimal(str(info_1.b)))
        x = float(x)

    return Coord_Pnt(x,y)

def isPointRedundant(mid_pnt : Coord_Pnt, pnt1 : Coord_Pnt, pnt2 : Coord_Pnt) -> bool:

    info_1 = Line_Info(mid_pnt,pnt1)
    info_2 = Line_Info(mid_pnt,pnt2)

    if info_1.m == info_2.m and info_1.b == info_2.b:
        return True

    return False
