"""Colormaps from matplotlib

Matplotlib is licensed under what looks like a modified MIT style license,
which is compatible with the GPL.
"""
import re
import numpy as np
from numpy import ma


def is_iterable(obj):
    'return true if *obj* is iterable'
    try: len(obj)
    except: return 0
    return 1

def makeMappingArray(N, data):
    """Create an *N* -element 1-d lookup table

    *data* represented by a list of x,y0,y1 mapping correspondences.
    Each element in this list represents how a value between 0 and 1
    (inclusive) represented by x is mapped to a corresponding value
    between 0 and 1 (inclusive). The two values of y are to allow
    for discontinuous mapping functions (say as might be found in a
    sawtooth) where y0 represents the value of y for values of x
    <= to that given, and y1 is the value to be used for x > than
    that given). The list must start with x=0, end with x=1, and
    all values of x must be in increasing order. Values between
    the given mapping points are determined by simple linear interpolation.

    The function returns an array "result" where ``result[x*(N-1)]``
    gives the closest value for values of x between 0 and 1.
    """
    try:
        adata = np.array(data)
    except:
        raise TypeError("data must be convertable to an array")
    shape = adata.shape
    if len(shape) != 2 and shape[1] != 3:
        raise ValueError("data must be nx3 format")

    x  = adata[:,0]
    y0 = adata[:,1]
    y1 = adata[:,2]

    if x[0] != 0. or x[-1] != 1.0:
        raise ValueError(
           "data mapping points must start with x=0. and end with x=1")
    if np.sometrue(np.sort(x)-x):
        raise ValueError(
           "data mapping points must have x in increasing order")
    # begin generation of lookup table
    x = x * (N-1)
    lut = np.zeros((N,), np.float)
    xind = np.arange(float(N))
    ind = np.searchsorted(x, xind)[1:-1]

    lut[1:-1] = ( ((xind[1:-1] - x[ind-1]) / (x[ind] - x[ind-1]))
                  * (y0[ind] - y1[ind-1]) + y1[ind-1])
    lut[0] = y1[0]
    lut[-1] = y0[-1]
    # ensure that the lut is confined to values between 0 and 1 by clipping it
    np.clip(lut, 0.0, 1.0)
    #lut = where(lut > 1., 1., lut)
    #lut = where(lut < 0., 0., lut)
    return lut


class Colormap:
    """Base class for all scalar to rgb mappings

        Important methods:

            * :meth:`set_bad`
            * :meth:`set_under`
            * :meth:`set_over`
    """
    def __init__(self, name, N=256):
        """
        Public class attributes:
            :attr:`N` : number of rgb quantization levels
            :attr:`name` : name of colormap

        """
        self.name = name
        self.N = N
        self._rgba_bad = (0.0, 0.0, 0.0, 0.0) # If bad, don't paint anything.
        self._rgba_under = None
        self._rgba_over = None
        self._i_under = N
        self._i_over = N+1
        self._i_bad = N+2
        self._isinit = False


    def __call__(self, X, alpha=1.0, bytes=False):
        """
        *X* is either a scalar or an array (of any dimension).
        If scalar, a tuple of rgba values is returned, otherwise
        an array with the new shape = oldshape+(4,). If the X-values
        are integers, then they are used as indices into the array.
        If they are floating point, then they must be in the
        interval (0.0, 1.0).
        Alpha must be a scalar.
        If bytes is False, the rgba values will be floats on a
        0-1 scale; if True, they will be uint8, 0-255.
        """

        if not self._isinit: self._init()
        alpha = min(alpha, 1.0) # alpha must be between 0 and 1
        alpha = max(alpha, 0.0)
        self._lut[:-3, -1] = alpha
        mask_bad = None
        if not is_iterable(X):
            vtype = 'scalar'
            xa = np.array([X])
        else:
            vtype = 'array'
            xma = ma.asarray(X)
            xa = xma.filled(0)
            mask_bad = ma.getmask(xma)
        if xa.dtype.char in np.typecodes['Float']:
            np.putmask(xa, xa==1.0, 0.9999999) #Treat 1.0 as slightly less than 1.
            xa = (xa * self.N).astype(int)
        # Set the over-range indices before the under-range;
        # otherwise the under-range values get converted to over-range.
        np.putmask(xa, xa>self.N-1, self._i_over)
        np.putmask(xa, xa<0, self._i_under)
        if mask_bad is not None and mask_bad.shape == xa.shape:
            np.putmask(xa, mask_bad, self._i_bad)
        if bytes:
            lut = (self._lut * 255).astype(np.uint8)
        else:
            lut = self._lut
        rgba = np.empty(shape=xa.shape+(4,), dtype=lut.dtype)
        lut.take(xa, axis=0, mode='clip', out=rgba)
                    #  twice as fast as lut[xa];
                    #  using the clip or wrap mode and providing an
                    #  output array speeds it up a little more.
        if vtype == 'scalar':
            rgba = tuple(rgba[0,:])
        return rgba

    def set_bad(self, color = 'k', alpha = 1.0):
        '''Set color to be used for masked values.
        '''
        self._rgba_bad = colorConverter.to_rgba(color, alpha)
        if self._isinit: self._set_extremes()

    def set_under(self, color = 'k', alpha = 1.0):
        '''Set color to be used for low out-of-range values.
           Requires norm.clip = False
        '''
        self._rgba_under = colorConverter.to_rgba(color, alpha)
        if self._isinit: self._set_extremes()

    def set_over(self, color = 'k', alpha = 1.0):
        '''Set color to be used for high out-of-range values.
           Requires norm.clip = False
        '''
        self._rgba_over = colorConverter.to_rgba(color, alpha)
        if self._isinit: self._set_extremes()

    def _set_extremes(self):
        if self._rgba_under:
            self._lut[self._i_under] = self._rgba_under
        else:
            self._lut[self._i_under] = self._lut[0]
        if self._rgba_over:
            self._lut[self._i_over] = self._rgba_over
        else:
            self._lut[self._i_over] = self._lut[self.N-1]
        self._lut[self._i_bad] = self._rgba_bad

    def _init():
        '''Generate the lookup table, self._lut'''
        raise NotImplementedError("Abstract class only")

    def is_gray(self):
        if not self._isinit: self._init()
        return (np.alltrue(self._lut[:,0] == self._lut[:,1])
                    and np.alltrue(self._lut[:,0] == self._lut[:,2]))


class LinearSegmentedColormap(Colormap):
    """Colormap objects based on lookup tables using linear segments.

    The lookup transfer function is a simple linear function between
    defined intensities. There is no limit to the number of segments
    that may be defined. Though as the segment intervals start containing
    fewer and fewer array locations, there will be inevitable quantization
    errors
    """
    def __init__(self, name, segmentdata, N=256):
        """Create color map from linear mapping segments

        segmentdata argument is a dictionary with a red, green and blue
        entries. Each entry should be a list of x, y0, y1 tuples.
        See makeMappingArray for details
        """
        self.monochrome = False  # True only if all colors in map are identical;
                                 # needed for contouring.
        Colormap.__init__(self, name, N)
        self._segmentdata = segmentdata

    def _init(self):
        self._lut = np.ones((self.N + 3, 4), np.float)
        self._lut[:-3, 0] = makeMappingArray(self.N, self._segmentdata['red'])
        self._lut[:-3, 1] = makeMappingArray(self.N, self._segmentdata['green'])
        self._lut[:-3, 2] = makeMappingArray(self.N, self._segmentdata['blue'])
        self._isinit = True
        self._set_extremes()


LUTSIZE = 256

_binary_data = {
    'red'  :  ((0., 1., 1.), (1., 0., 0.)),
    'green':  ((0., 1., 1.), (1., 0., 0.)),
    'blue' :  ((0., 1., 1.), (1., 0., 0.))
    }


_bone_data = {'red':   ((0., 0., 0.),(1.0, 1.0, 1.0)),
              'green': ((0., 0., 0.),(1.0, 1.0, 1.0)),
              'blue':  ((0., 0., 0.),(1.0, 1.0, 1.0))}


_autumn_data = {'red':   ((0., 1.0, 1.0),(1.0, 1.0, 1.0)),
                'green': ((0., 0., 0.),(1.0, 1.0, 1.0)),
                'blue':  ((0., 0., 0.),(1.0, 0., 0.))}

_bone_data = {'red':   ((0., 0., 0.),(0.746032, 0.652778, 0.652778),(1.0, 1.0, 1.0)),
              'green': ((0., 0., 0.),(0.365079, 0.319444, 0.319444),
                        (0.746032, 0.777778, 0.777778),(1.0, 1.0, 1.0)),
              'blue':  ((0., 0., 0.),(0.365079, 0.444444, 0.444444),(1.0, 1.0, 1.0))}

_cool_data = {'red':   ((0., 0., 0.), (1.0, 1.0, 1.0)),
              'green': ((0., 1., 1.), (1.0, 0.,  0.)),
              'blue':  ((0., 1., 1.), (1.0, 1.,  1.))}

_copper_data = {'red':   ((0., 0., 0.),(0.809524, 1.000000, 1.000000),(1.0, 1.0, 1.0)),
                'green': ((0., 0., 0.),(1.0, 0.7812, 0.7812)),
                'blue':  ((0., 0., 0.),(1.0, 0.4975, 0.4975))}

_flag_data = {'red':   ((0., 1., 1.),(0.015873, 1.000000, 1.000000),
                        (0.031746, 0.000000, 0.000000),(0.047619, 0.000000, 0.000000),
                        (0.063492, 1.000000, 1.000000),(0.079365, 1.000000, 1.000000),
                        (0.095238, 0.000000, 0.000000),(0.111111, 0.000000, 0.000000),
                        (0.126984, 1.000000, 1.000000),(0.142857, 1.000000, 1.000000),
                        (0.158730, 0.000000, 0.000000),(0.174603, 0.000000, 0.000000),
                        (0.190476, 1.000000, 1.000000),(0.206349, 1.000000, 1.000000),
                        (0.222222, 0.000000, 0.000000),(0.238095, 0.000000, 0.000000),
                        (0.253968, 1.000000, 1.000000),(0.269841, 1.000000, 1.000000),
                        (0.285714, 0.000000, 0.000000),(0.301587, 0.000000, 0.000000),
                        (0.317460, 1.000000, 1.000000),(0.333333, 1.000000, 1.000000),
                        (0.349206, 0.000000, 0.000000),(0.365079, 0.000000, 0.000000),
                        (0.380952, 1.000000, 1.000000),(0.396825, 1.000000, 1.000000),
                        (0.412698, 0.000000, 0.000000),(0.428571, 0.000000, 0.000000),
                        (0.444444, 1.000000, 1.000000),(0.460317, 1.000000, 1.000000),
                        (0.476190, 0.000000, 0.000000),(0.492063, 0.000000, 0.000000),
                        (0.507937, 1.000000, 1.000000),(0.523810, 1.000000, 1.000000),
                        (0.539683, 0.000000, 0.000000),(0.555556, 0.000000, 0.000000),
                        (0.571429, 1.000000, 1.000000),(0.587302, 1.000000, 1.000000),
                        (0.603175, 0.000000, 0.000000),(0.619048, 0.000000, 0.000000),
                        (0.634921, 1.000000, 1.000000),(0.650794, 1.000000, 1.000000),
                        (0.666667, 0.000000, 0.000000),(0.682540, 0.000000, 0.000000),
                        (0.698413, 1.000000, 1.000000),(0.714286, 1.000000, 1.000000),
                        (0.730159, 0.000000, 0.000000),(0.746032, 0.000000, 0.000000),
                        (0.761905, 1.000000, 1.000000),(0.777778, 1.000000, 1.000000),
                        (0.793651, 0.000000, 0.000000),(0.809524, 0.000000, 0.000000),
                        (0.825397, 1.000000, 1.000000),(0.841270, 1.000000, 1.000000),
                        (0.857143, 0.000000, 0.000000),(0.873016, 0.000000, 0.000000),
                        (0.888889, 1.000000, 1.000000),(0.904762, 1.000000, 1.000000),
                        (0.920635, 0.000000, 0.000000),(0.936508, 0.000000, 0.000000),
                        (0.952381, 1.000000, 1.000000),(0.968254, 1.000000, 1.000000),
                        (0.984127, 0.000000, 0.000000),(1.0, 0., 0.)),
              'green': ((0., 0., 0.),(0.015873, 1.000000, 1.000000),
                        (0.031746, 0.000000, 0.000000),(0.063492, 0.000000, 0.000000),
                        (0.079365, 1.000000, 1.000000),(0.095238, 0.000000, 0.000000),
                        (0.126984, 0.000000, 0.000000),(0.142857, 1.000000, 1.000000),
                        (0.158730, 0.000000, 0.000000),(0.190476, 0.000000, 0.000000),
                        (0.206349, 1.000000, 1.000000),(0.222222, 0.000000, 0.000000),
                        (0.253968, 0.000000, 0.000000),(0.269841, 1.000000, 1.000000),
                        (0.285714, 0.000000, 0.000000),(0.317460, 0.000000, 0.000000),
                        (0.333333, 1.000000, 1.000000),(0.349206, 0.000000, 0.000000),
                        (0.380952, 0.000000, 0.000000),(0.396825, 1.000000, 1.000000),
                        (0.412698, 0.000000, 0.000000),(0.444444, 0.000000, 0.000000),
                        (0.460317, 1.000000, 1.000000),(0.476190, 0.000000, 0.000000),
                        (0.507937, 0.000000, 0.000000),(0.523810, 1.000000, 1.000000),
                        (0.539683, 0.000000, 0.000000),(0.571429, 0.000000, 0.000000),
                        (0.587302, 1.000000, 1.000000),(0.603175, 0.000000, 0.000000),
                        (0.634921, 0.000000, 0.000000),(0.650794, 1.000000, 1.000000),
                        (0.666667, 0.000000, 0.000000),(0.698413, 0.000000, 0.000000),
                        (0.714286, 1.000000, 1.000000),(0.730159, 0.000000, 0.000000),
                        (0.761905, 0.000000, 0.000000),(0.777778, 1.000000, 1.000000),
                        (0.793651, 0.000000, 0.000000),(0.825397, 0.000000, 0.000000),
                        (0.841270, 1.000000, 1.000000),(0.857143, 0.000000, 0.000000),
                        (0.888889, 0.000000, 0.000000),(0.904762, 1.000000, 1.000000),
                        (0.920635, 0.000000, 0.000000),(0.952381, 0.000000, 0.000000),
                        (0.968254, 1.000000, 1.000000),(0.984127, 0.000000, 0.000000),
                        (1.0, 0., 0.)),
              'blue':  ((0., 0., 0.),(0.015873, 1.000000, 1.000000),
                        (0.031746, 1.000000, 1.000000),(0.047619, 0.000000, 0.000000),
                        (0.063492, 0.000000, 0.000000),(0.079365, 1.000000, 1.000000),
                        (0.095238, 1.000000, 1.000000),(0.111111, 0.000000, 0.000000),
                        (0.126984, 0.000000, 0.000000),(0.142857, 1.000000, 1.000000),
                        (0.158730, 1.000000, 1.000000),(0.174603, 0.000000, 0.000000),
                        (0.190476, 0.000000, 0.000000),(0.206349, 1.000000, 1.000000),
                        (0.222222, 1.000000, 1.000000),(0.238095, 0.000000, 0.000000),
                        (0.253968, 0.000000, 0.000000),(0.269841, 1.000000, 1.000000),
                        (0.285714, 1.000000, 1.000000),(0.301587, 0.000000, 0.000000),
                        (0.317460, 0.000000, 0.000000),(0.333333, 1.000000, 1.000000),
                        (0.349206, 1.000000, 1.000000),(0.365079, 0.000000, 0.000000),
                        (0.380952, 0.000000, 0.000000),(0.396825, 1.000000, 1.000000),
                        (0.412698, 1.000000, 1.000000),(0.428571, 0.000000, 0.000000),
                        (0.444444, 0.000000, 0.000000),(0.460317, 1.000000, 1.000000),
                        (0.476190, 1.000000, 1.000000),(0.492063, 0.000000, 0.000000),
                        (0.507937, 0.000000, 0.000000),(0.523810, 1.000000, 1.000000),
                        (0.539683, 1.000000, 1.000000),(0.555556, 0.000000, 0.000000),
                        (0.571429, 0.000000, 0.000000),(0.587302, 1.000000, 1.000000),
                        (0.603175, 1.000000, 1.000000),(0.619048, 0.000000, 0.000000),
                        (0.634921, 0.000000, 0.000000),(0.650794, 1.000000, 1.000000),
                        (0.666667, 1.000000, 1.000000),(0.682540, 0.000000, 0.000000),
                        (0.698413, 0.000000, 0.000000),(0.714286, 1.000000, 1.000000),
                        (0.730159, 1.000000, 1.000000),(0.746032, 0.000000, 0.000000),
                        (0.761905, 0.000000, 0.000000),(0.777778, 1.000000, 1.000000),
                        (0.793651, 1.000000, 1.000000),(0.809524, 0.000000, 0.000000),
                        (0.825397, 0.000000, 0.000000),(0.841270, 1.000000, 1.000000),
                        (0.857143, 1.000000, 1.000000),(0.873016, 0.000000, 0.000000),
                        (0.888889, 0.000000, 0.000000),(0.904762, 1.000000, 1.000000),
                        (0.920635, 1.000000, 1.000000),(0.936508, 0.000000, 0.000000),
                        (0.952381, 0.000000, 0.000000),(0.968254, 1.000000, 1.000000),
                        (0.984127, 1.000000, 1.000000),(1.0, 0., 0.))}

_gray_data =  {'red':   ((0., 0, 0), (1., 1, 1)),
               'green': ((0., 0, 0), (1., 1, 1)),
               'blue':  ((0., 0, 0), (1., 1, 1))}

_hot_data = {'red':   ((0., 0.0416, 0.0416),(0.365079, 1.000000, 1.000000),(1.0, 1.0, 1.0)),
             'green': ((0., 0., 0.),(0.365079, 0.000000, 0.000000),
                       (0.746032, 1.000000, 1.000000),(1.0, 1.0, 1.0)),
             'blue':  ((0., 0., 0.),(0.746032, 0.000000, 0.000000),(1.0, 1.0, 1.0))}

_hsv_data = {'red':   ((0., 1., 1.),(0.158730, 1.000000, 1.000000),
                       (0.174603, 0.968750, 0.968750),(0.333333, 0.031250, 0.031250),
                       (0.349206, 0.000000, 0.000000),(0.666667, 0.000000, 0.000000),
                       (0.682540, 0.031250, 0.031250),(0.841270, 0.968750, 0.968750),
                       (0.857143, 1.000000, 1.000000),(1.0, 1.0, 1.0)),
             'green': ((0., 0., 0.),(0.158730, 0.937500, 0.937500),
                       (0.174603, 1.000000, 1.000000),(0.507937, 1.000000, 1.000000),
                       (0.666667, 0.062500, 0.062500),(0.682540, 0.000000, 0.000000),
                       (1.0, 0., 0.)),
             'blue':  ((0., 0., 0.),(0.333333, 0.000000, 0.000000),
                       (0.349206, 0.062500, 0.062500),(0.507937, 1.000000, 1.000000),
                       (0.841270, 1.000000, 1.000000),(0.857143, 0.937500, 0.937500),
                       (1.0, 0.09375, 0.09375))}

_jet_data =   {'red':   ((0., 0, 0), (0.35, 0, 0), (0.66, 1, 1), (0.89,1, 1),
                         (1, 0.5, 0.5)),
               'green': ((0., 0, 0), (0.125,0, 0), (0.375,1, 1), (0.64,1, 1),
                         (0.91,0,0), (1, 0, 0)),
               'blue':  ((0., 0.5, 0.5), (0.11, 1, 1), (0.34, 1, 1), (0.65,0, 0),
                         (1, 0, 0))}

_pink_data = {'red':   ((0., 0.1178, 0.1178),(0.015873, 0.195857, 0.195857),
                        (0.031746, 0.250661, 0.250661),(0.047619, 0.295468, 0.295468),
                        (0.063492, 0.334324, 0.334324),(0.079365, 0.369112, 0.369112),
                        (0.095238, 0.400892, 0.400892),(0.111111, 0.430331, 0.430331),
                        (0.126984, 0.457882, 0.457882),(0.142857, 0.483867, 0.483867),
                        (0.158730, 0.508525, 0.508525),(0.174603, 0.532042, 0.532042),
                        (0.190476, 0.554563, 0.554563),(0.206349, 0.576204, 0.576204),
                        (0.222222, 0.597061, 0.597061),(0.238095, 0.617213, 0.617213),
                        (0.253968, 0.636729, 0.636729),(0.269841, 0.655663, 0.655663),
                        (0.285714, 0.674066, 0.674066),(0.301587, 0.691980, 0.691980),
                        (0.317460, 0.709441, 0.709441),(0.333333, 0.726483, 0.726483),
                        (0.349206, 0.743134, 0.743134),(0.365079, 0.759421, 0.759421),
                        (0.380952, 0.766356, 0.766356),(0.396825, 0.773229, 0.773229),
                        (0.412698, 0.780042, 0.780042),(0.428571, 0.786796, 0.786796),
                        (0.444444, 0.793492, 0.793492),(0.460317, 0.800132, 0.800132),
                        (0.476190, 0.806718, 0.806718),(0.492063, 0.813250, 0.813250),
                        (0.507937, 0.819730, 0.819730),(0.523810, 0.826160, 0.826160),
                        (0.539683, 0.832539, 0.832539),(0.555556, 0.838870, 0.838870),
                        (0.571429, 0.845154, 0.845154),(0.587302, 0.851392, 0.851392),
                        (0.603175, 0.857584, 0.857584),(0.619048, 0.863731, 0.863731),
                        (0.634921, 0.869835, 0.869835),(0.650794, 0.875897, 0.875897),
                        (0.666667, 0.881917, 0.881917),(0.682540, 0.887896, 0.887896),
                        (0.698413, 0.893835, 0.893835),(0.714286, 0.899735, 0.899735),
                        (0.730159, 0.905597, 0.905597),(0.746032, 0.911421, 0.911421),
                        (0.761905, 0.917208, 0.917208),(0.777778, 0.922958, 0.922958),
                        (0.793651, 0.928673, 0.928673),(0.809524, 0.934353, 0.934353),
                        (0.825397, 0.939999, 0.939999),(0.841270, 0.945611, 0.945611),
                        (0.857143, 0.951190, 0.951190),(0.873016, 0.956736, 0.956736),
                        (0.888889, 0.962250, 0.962250),(0.904762, 0.967733, 0.967733),
                        (0.920635, 0.973185, 0.973185),(0.936508, 0.978607, 0.978607),
                        (0.952381, 0.983999, 0.983999),(0.968254, 0.989361, 0.989361),
                        (0.984127, 0.994695, 0.994695),(1.0, 1.0, 1.0)),
              'green': ((0., 0., 0.),(0.015873, 0.102869, 0.102869),
                        (0.031746, 0.145479, 0.145479),(0.047619, 0.178174, 0.178174),
                        (0.063492, 0.205738, 0.205738),(0.079365, 0.230022, 0.230022),
                        (0.095238, 0.251976, 0.251976),(0.111111, 0.272166, 0.272166),
                        (0.126984, 0.290957, 0.290957),(0.142857, 0.308607, 0.308607),
                        (0.158730, 0.325300, 0.325300),(0.174603, 0.341178, 0.341178),
                        (0.190476, 0.356348, 0.356348),(0.206349, 0.370899, 0.370899),
                        (0.222222, 0.384900, 0.384900),(0.238095, 0.398410, 0.398410),
                        (0.253968, 0.411476, 0.411476),(0.269841, 0.424139, 0.424139),
                        (0.285714, 0.436436, 0.436436),(0.301587, 0.448395, 0.448395),
                        (0.317460, 0.460044, 0.460044),(0.333333, 0.471405, 0.471405),
                        (0.349206, 0.482498, 0.482498),(0.365079, 0.493342, 0.493342),
                        (0.380952, 0.517549, 0.517549),(0.396825, 0.540674, 0.540674),
                        (0.412698, 0.562849, 0.562849),(0.428571, 0.584183, 0.584183),
                        (0.444444, 0.604765, 0.604765),(0.460317, 0.624669, 0.624669),
                        (0.476190, 0.643958, 0.643958),(0.492063, 0.662687, 0.662687),
                        (0.507937, 0.680900, 0.680900),(0.523810, 0.698638, 0.698638),
                        (0.539683, 0.715937, 0.715937),(0.555556, 0.732828, 0.732828),
                        (0.571429, 0.749338, 0.749338),(0.587302, 0.765493, 0.765493),
                        (0.603175, 0.781313, 0.781313),(0.619048, 0.796819, 0.796819),
                        (0.634921, 0.812029, 0.812029),(0.650794, 0.826960, 0.826960),
                        (0.666667, 0.841625, 0.841625),(0.682540, 0.856040, 0.856040),
                        (0.698413, 0.870216, 0.870216),(0.714286, 0.884164, 0.884164),
                        (0.730159, 0.897896, 0.897896),(0.746032, 0.911421, 0.911421),
                        (0.761905, 0.917208, 0.917208),(0.777778, 0.922958, 0.922958),
                        (0.793651, 0.928673, 0.928673),(0.809524, 0.934353, 0.934353),
                        (0.825397, 0.939999, 0.939999),(0.841270, 0.945611, 0.945611),
                        (0.857143, 0.951190, 0.951190),(0.873016, 0.956736, 0.956736),
                        (0.888889, 0.962250, 0.962250),(0.904762, 0.967733, 0.967733),
                        (0.920635, 0.973185, 0.973185),(0.936508, 0.978607, 0.978607),
                        (0.952381, 0.983999, 0.983999),(0.968254, 0.989361, 0.989361),
                        (0.984127, 0.994695, 0.994695),(1.0, 1.0, 1.0)),
              'blue':  ((0., 0., 0.),(0.015873, 0.102869, 0.102869),
                        (0.031746, 0.145479, 0.145479),(0.047619, 0.178174, 0.178174),
                        (0.063492, 0.205738, 0.205738),(0.079365, 0.230022, 0.230022),
                        (0.095238, 0.251976, 0.251976),(0.111111, 0.272166, 0.272166),
                        (0.126984, 0.290957, 0.290957),(0.142857, 0.308607, 0.308607),
                        (0.158730, 0.325300, 0.325300),(0.174603, 0.341178, 0.341178),
                        (0.190476, 0.356348, 0.356348),(0.206349, 0.370899, 0.370899),
                        (0.222222, 0.384900, 0.384900),(0.238095, 0.398410, 0.398410),
                        (0.253968, 0.411476, 0.411476),(0.269841, 0.424139, 0.424139),
                        (0.285714, 0.436436, 0.436436),(0.301587, 0.448395, 0.448395),
                        (0.317460, 0.460044, 0.460044),(0.333333, 0.471405, 0.471405),
                        (0.349206, 0.482498, 0.482498),(0.365079, 0.493342, 0.493342),
                        (0.380952, 0.503953, 0.503953),(0.396825, 0.514344, 0.514344),
                        (0.412698, 0.524531, 0.524531),(0.428571, 0.534522, 0.534522),
                        (0.444444, 0.544331, 0.544331),(0.460317, 0.553966, 0.553966),
                        (0.476190, 0.563436, 0.563436),(0.492063, 0.572750, 0.572750),
                        (0.507937, 0.581914, 0.581914),(0.523810, 0.590937, 0.590937),
                        (0.539683, 0.599824, 0.599824),(0.555556, 0.608581, 0.608581),
                        (0.571429, 0.617213, 0.617213),(0.587302, 0.625727, 0.625727),
                        (0.603175, 0.634126, 0.634126),(0.619048, 0.642416, 0.642416),
                        (0.634921, 0.650600, 0.650600),(0.650794, 0.658682, 0.658682),
                        (0.666667, 0.666667, 0.666667),(0.682540, 0.674556, 0.674556),
                        (0.698413, 0.682355, 0.682355),(0.714286, 0.690066, 0.690066),
                        (0.730159, 0.697691, 0.697691),(0.746032, 0.705234, 0.705234),
                        (0.761905, 0.727166, 0.727166),(0.777778, 0.748455, 0.748455),
                        (0.793651, 0.769156, 0.769156),(0.809524, 0.789314, 0.789314),
                        (0.825397, 0.808969, 0.808969),(0.841270, 0.828159, 0.828159),
                        (0.857143, 0.846913, 0.846913),(0.873016, 0.865261, 0.865261),
                        (0.888889, 0.883229, 0.883229),(0.904762, 0.900837, 0.900837),
                        (0.920635, 0.918109, 0.918109),(0.936508, 0.935061, 0.935061),
                        (0.952381, 0.951711, 0.951711),(0.968254, 0.968075, 0.968075),
                        (0.984127, 0.984167, 0.984167),(1.0, 1.0, 1.0))}

_prism_data = {'red':   ((0., 1., 1.),(0.031746, 1.000000, 1.000000),
                         (0.047619, 0.000000, 0.000000),(0.063492, 0.000000, 0.000000),
                         (0.079365, 0.666667, 0.666667),(0.095238, 1.000000, 1.000000),
                         (0.126984, 1.000000, 1.000000),(0.142857, 0.000000, 0.000000),
                         (0.158730, 0.000000, 0.000000),(0.174603, 0.666667, 0.666667),
                         (0.190476, 1.000000, 1.000000),(0.222222, 1.000000, 1.000000),
                         (0.238095, 0.000000, 0.000000),(0.253968, 0.000000, 0.000000),
                         (0.269841, 0.666667, 0.666667),(0.285714, 1.000000, 1.000000),
                         (0.317460, 1.000000, 1.000000),(0.333333, 0.000000, 0.000000),
                         (0.349206, 0.000000, 0.000000),(0.365079, 0.666667, 0.666667),
                         (0.380952, 1.000000, 1.000000),(0.412698, 1.000000, 1.000000),
                         (0.428571, 0.000000, 0.000000),(0.444444, 0.000000, 0.000000),
                         (0.460317, 0.666667, 0.666667),(0.476190, 1.000000, 1.000000),
                         (0.507937, 1.000000, 1.000000),(0.523810, 0.000000, 0.000000),
                         (0.539683, 0.000000, 0.000000),(0.555556, 0.666667, 0.666667),
                         (0.571429, 1.000000, 1.000000),(0.603175, 1.000000, 1.000000),
                         (0.619048, 0.000000, 0.000000),(0.634921, 0.000000, 0.000000),
                         (0.650794, 0.666667, 0.666667),(0.666667, 1.000000, 1.000000),
                         (0.698413, 1.000000, 1.000000),(0.714286, 0.000000, 0.000000),
                         (0.730159, 0.000000, 0.000000),(0.746032, 0.666667, 0.666667),
                         (0.761905, 1.000000, 1.000000),(0.793651, 1.000000, 1.000000),
                         (0.809524, 0.000000, 0.000000),(0.825397, 0.000000, 0.000000),
                         (0.841270, 0.666667, 0.666667),(0.857143, 1.000000, 1.000000),
                         (0.888889, 1.000000, 1.000000),(0.904762, 0.000000, 0.000000),
                         (0.920635, 0.000000, 0.000000),(0.936508, 0.666667, 0.666667),
                         (0.952381, 1.000000, 1.000000),(0.984127, 1.000000, 1.000000),
                         (1.0, 0.0, 0.0)),
               'green': ((0., 0., 0.),(0.031746, 1.000000, 1.000000),
                         (0.047619, 1.000000, 1.000000),(0.063492, 0.000000, 0.000000),
                         (0.095238, 0.000000, 0.000000),(0.126984, 1.000000, 1.000000),
                         (0.142857, 1.000000, 1.000000),(0.158730, 0.000000, 0.000000),
                         (0.190476, 0.000000, 0.000000),(0.222222, 1.000000, 1.000000),
                         (0.238095, 1.000000, 1.000000),(0.253968, 0.000000, 0.000000),
                         (0.285714, 0.000000, 0.000000),(0.317460, 1.000000, 1.000000),
                         (0.333333, 1.000000, 1.000000),(0.349206, 0.000000, 0.000000),
                         (0.380952, 0.000000, 0.000000),(0.412698, 1.000000, 1.000000),
                         (0.428571, 1.000000, 1.000000),(0.444444, 0.000000, 0.000000),
                         (0.476190, 0.000000, 0.000000),(0.507937, 1.000000, 1.000000),
                         (0.523810, 1.000000, 1.000000),(0.539683, 0.000000, 0.000000),
                         (0.571429, 0.000000, 0.000000),(0.603175, 1.000000, 1.000000),
                         (0.619048, 1.000000, 1.000000),(0.634921, 0.000000, 0.000000),
                         (0.666667, 0.000000, 0.000000),(0.698413, 1.000000, 1.000000),
                         (0.714286, 1.000000, 1.000000),(0.730159, 0.000000, 0.000000),
                         (0.761905, 0.000000, 0.000000),(0.793651, 1.000000, 1.000000),
                         (0.809524, 1.000000, 1.000000),(0.825397, 0.000000, 0.000000),
                         (0.857143, 0.000000, 0.000000),(0.888889, 1.000000, 1.000000),
                         (0.904762, 1.000000, 1.000000),(0.920635, 0.000000, 0.000000),
                         (0.952381, 0.000000, 0.000000),(0.984127, 1.000000, 1.000000),
                         (1.0, 1.0, 1.0)),
               'blue':  ((0., 0., 0.),(0.047619, 0.000000, 0.000000),
                         (0.063492, 1.000000, 1.000000),(0.079365, 1.000000, 1.000000),
                         (0.095238, 0.000000, 0.000000),(0.142857, 0.000000, 0.000000),
                         (0.158730, 1.000000, 1.000000),(0.174603, 1.000000, 1.000000),
                         (0.190476, 0.000000, 0.000000),(0.238095, 0.000000, 0.000000),
                         (0.253968, 1.000000, 1.000000),(0.269841, 1.000000, 1.000000),
                         (0.285714, 0.000000, 0.000000),(0.333333, 0.000000, 0.000000),
                         (0.349206, 1.000000, 1.000000),(0.365079, 1.000000, 1.000000),
                         (0.380952, 0.000000, 0.000000),(0.428571, 0.000000, 0.000000),
                         (0.444444, 1.000000, 1.000000),(0.460317, 1.000000, 1.000000),
                         (0.476190, 0.000000, 0.000000),(0.523810, 0.000000, 0.000000),
                         (0.539683, 1.000000, 1.000000),(0.555556, 1.000000, 1.000000),
                         (0.571429, 0.000000, 0.000000),(0.619048, 0.000000, 0.000000),
                         (0.634921, 1.000000, 1.000000),(0.650794, 1.000000, 1.000000),
                         (0.666667, 0.000000, 0.000000),(0.714286, 0.000000, 0.000000),
                         (0.730159, 1.000000, 1.000000),(0.746032, 1.000000, 1.000000),
                         (0.761905, 0.000000, 0.000000),(0.809524, 0.000000, 0.000000),
                         (0.825397, 1.000000, 1.000000),(0.841270, 1.000000, 1.000000),
                         (0.857143, 0.000000, 0.000000),(0.904762, 0.000000, 0.000000),
                         (0.920635, 1.000000, 1.000000),(0.936508, 1.000000, 1.000000),
                         (0.952381, 0.000000, 0.000000),(1.0, 0.0, 0.0))}

_spring_data = {'red':   ((0., 1., 1.),(1.0, 1.0, 1.0)),
                'green': ((0., 0., 0.),(1.0, 1.0, 1.0)),
                'blue':  ((0., 1., 1.),(1.0, 0.0, 0.0))}


_summer_data = {'red':   ((0., 0., 0.),(1.0, 1.0, 1.0)),
                'green': ((0., 0.5, 0.5),(1.0, 1.0, 1.0)),
                'blue':  ((0., 0.4, 0.4),(1.0, 0.4, 0.4))}


_winter_data = {'red':   ((0., 0., 0.),(1.0, 0.0, 0.0)),
                'green': ((0., 0., 0.),(1.0, 1.0, 1.0)),
                'blue':  ((0., 1., 1.),(1.0, 0.5, 0.5))}

_spectral_data = {'red': [(0.0, 0.0, 0.0), (0.05, 0.4667, 0.4667),
                          (0.10, 0.5333, 0.5333), (0.15, 0.0, 0.0),
                          (0.20, 0.0, 0.0), (0.25, 0.0, 0.0),
                          (0.30, 0.0, 0.0), (0.35, 0.0, 0.0),
                          (0.40, 0.0, 0.0), (0.45, 0.0, 0.0),
                          (0.50, 0.0, 0.0), (0.55, 0.0, 0.0),
                          (0.60, 0.0, 0.0), (0.65, 0.7333, 0.7333),
                          (0.70, 0.9333, 0.9333), (0.75, 1.0, 1.0),
                          (0.80, 1.0, 1.0), (0.85, 1.0, 1.0),
                          (0.90, 0.8667, 0.8667), (0.95, 0.80, 0.80),
                          (1.0, 0.80, 0.80)],
                  'green': [(0.0, 0.0, 0.0), (0.05, 0.0, 0.0),
                            (0.10, 0.0, 0.0), (0.15, 0.0, 0.0),
                            (0.20, 0.0, 0.0), (0.25, 0.4667, 0.4667),
                            (0.30, 0.6000, 0.6000), (0.35, 0.6667, 0.6667),
                            (0.40, 0.6667, 0.6667), (0.45, 0.6000, 0.6000),
                            (0.50, 0.7333, 0.7333), (0.55, 0.8667, 0.8667),
                            (0.60, 1.0, 1.0), (0.65, 1.0, 1.0),
                            (0.70, 0.9333, 0.9333), (0.75, 0.8000, 0.8000),
                            (0.80, 0.6000, 0.6000), (0.85, 0.0, 0.0),
                            (0.90, 0.0, 0.0), (0.95, 0.0, 0.0),
                            (1.0, 0.80, 0.80)],
                  'blue': [(0.0, 0.0, 0.0), (0.05, 0.5333, 0.5333),
                           (0.10, 0.6000, 0.6000), (0.15, 0.6667, 0.6667),
                           (0.20, 0.8667, 0.8667), (0.25, 0.8667, 0.8667),
                           (0.30, 0.8667, 0.8667), (0.35, 0.6667, 0.6667),
                           (0.40, 0.5333, 0.5333), (0.45, 0.0, 0.0),
                           (0.5, 0.0, 0.0), (0.55, 0.0, 0.0),
                           (0.60, 0.0, 0.0), (0.65, 0.0, 0.0),
                           (0.70, 0.0, 0.0), (0.75, 0.0, 0.0),
                           (0.80, 0.0, 0.0), (0.85, 0.0, 0.0),
                           (0.90, 0.0, 0.0), (0.95, 0.0, 0.0),
                           (1.0, 0.80, 0.80)]}


datad = {
    'autumn': _autumn_data,
    'bone':   _bone_data,
    'binary':   _binary_data,
    'cool':   _cool_data,
    'copper': _copper_data,
    'flag':   _flag_data,
    'gray' :  _gray_data,
    'hot':    _hot_data,
    'hsv':    _hsv_data,
    'jet' :   _jet_data,
    'pink':   _pink_data,
    'prism':  _prism_data,
    'spring': _spring_data,
    'summer': _summer_data,
    'winter': _winter_data,
    'spectral': _spectral_data
    }

_colormaps = {}

def getColormap(name):
    try:
        return _colormaps[name]
    except KeyError:
        pass
    try:
        data = datad[name]
    except KeyError:
        return None
    cmap = LinearSegmentedColormap(name, data, LUTSIZE)
    _colormaps[name] = cmap
    return cmap

def getColormapNames():
    names = datad.keys()
    names.sort()
    return names
