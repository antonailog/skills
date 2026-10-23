#!/usr/bin/env python3
"""OKLCH ↔ sRGB 转换与对比度计算。无第三方依赖。"""
import math
def _lin(c): return c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4
def _gam(c): c=max(0.0,min(1.0,c)); return 12.92*c if c<=0.0031308 else 1.055*c**(1/2.4)-0.055
def hex_to_rgb(h): h=h.lstrip('#'); return tuple(int(h[i:i+2],16)/255 for i in (0,2,4))
def rgb_to_hex(r,g,b): return '#%02x%02x%02x'%tuple(round(max(0,min(1,v))*255) for v in (r,g,b))
def rgb_to_oklab(r,g,b):
    r,g,b=_lin(r),_lin(g),_lin(b)
    l=0.4122214708*r+0.5363325363*g+0.0514459929*b; m=0.2119034982*r+0.6806995451*g+0.1073969566*b; s=0.0883024619*r+0.2817188376*g+0.6299787005*b
    l,m,s=l**(1/3),m**(1/3),s**(1/3)
    return (0.2104542553*l+0.7936177850*m-0.0040720468*s, 1.9779984951*l-2.4285922050*m+0.4505937099*s, 0.0259040371*l+0.7827717662*m-0.8086757660*s)
def oklab_to_rgb_linear(L,a,b):
    l=L+0.3963377774*a+0.2158037573*b; m=L-0.1055613458*a-0.0638541728*b; s=L-0.0894841775*a-1.2914855480*b
    l,m,s=l**3,m**3,s**3
    return (4.0767416621*l-3.3077115913*m+0.2309699292*s, -1.2684380046*l+2.6097574011*m-0.3413193965*s, -0.0041960863*l-0.7034186147*m+1.7076147010*s)
def hex_to_oklch(h):
    L,a,b=rgb_to_oklab(*hex_to_rgb(h)); return (L, math.hypot(a,b), math.degrees(math.atan2(b,a))%360)
def oklch_to_hex(L,C,h):
    """超出 sRGB 色域时逐步降彩度直到进入色域。"""
    for _ in range(60):
        a=C*math.cos(math.radians(h)); b=C*math.sin(math.radians(h))
        r,g,bl=oklab_to_rgb_linear(L,a,b)
        if all(-0.0005<=v<=1.0005 for v in (r,g,bl)): return rgb_to_hex(_gam(r),_gam(g),_gam(bl))
        C*=0.96
    return rgb_to_hex(_gam(r),_gam(g),_gam(bl))
def luminance(h):
    r,g,b=(_lin(v) for v in hex_to_rgb(h)); return 0.2126*r+0.7152*g+0.0722*b
def contrast(h1,h2):
    a,b=luminance(h1),luminance(h2); a,b=max(a,b),min(a,b); return (a+0.05)/(b+0.05)
if __name__=='__main__':
    import sys
    for h in sys.argv[1:]: L,C,H=hex_to_oklch(h); print(h,f'L={L:.3f} C={C:.3f} h={H:.0f}')
