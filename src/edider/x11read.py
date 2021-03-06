#!/usr/bin/env python
# -*- coding: utf-8 -*-
from contextlib import contextmanager
from collections import namedtuple

from Xlib import X, display, Xatom
from Xlib.error import XError
from Xlib.ext import randr

from edider.parser import BaseMonitor
from builtins import bytes      # needed for python2 compatibility

Geometry = namedtuple('Geometry', 'x y width height')

@contextmanager
def get_window(i_screen=0):
    "Create & manage a x-window."
    screen = display.Display().screen(i_screen)
    window = screen.root.create_window(0, 0, 1, 1, 1, screen.root_depth)
    yield window
    window.destroy()

def get_connected_outputs(i_screen=0):
    "Yield the X11-index for each connected monitor"
    with get_window(i_screen) as window:
        res = randr.get_screen_resources(window)
        outputs = res.outputs
        for output in outputs:
            info = randr.get_output_info(window, output, 0)
            if info.connection == 0:
                yield output

CRTCInfo = namedtuple('CRTCInfo', ('idx', 'info'))
def crtc_info(*crtc_idx):
    with get_window() as win:
        for idx in crtc_idx:
            try:
                info = randr.get_crtc_info(win, idx, 0)._data
            except XError:      # will error if crtc == 0
                info = {}
            yield CRTCInfo(idx, info)

class X11Output(object):
    def __init__(self, idx):
        self.idx = idx

    @property
    def edid(self):
        try:
            return self._edid
        except AttributeError:
            pass
        PROPERTY_EDID = display.Display().intern_atom('EDID', only_if_exists=True)
        with get_window() as win:
            edid = randr.get_output_property(
                win,
                self.idx,
                PROPERTY_EDID,
                Xatom.INTEGER,
                0,
                400,
            )
            edid = bytes(edid.value)
            self._edid = edid
        return self._edid

    @property
    def idx_primary(self):
        with get_window(0) as window:
            return randr.get_output_primary(window).output

    @property
    def info(self):
        try:
            return self._info
        except AttributeError:
            pass
        with get_window() as win:
            self._info = randr.get_output_info(win, self.idx, 0)._data
        return self._info

    @property
    def output_name(self):
        return self.info['name']

    @property
    def crtc(self):
        return next(crtc_info(self.info['crtc']))

    @property
    def crtcs(self):
        return list(crtc_info(*self.info['crtcs']))

    def _get_modes(self):
        with get_window() as win:
            res = randr.get_screen_resources(win)
            modes = res._data['modes']
            modes = [x._data for x in modes]
            return modes

    @property
    def modes(self):
        try:
            return self._modes
        except AttributeError:
            self._modes = self._get_modes()
            return self._modes

    @property
    def preferred_mode(self):
        npref = self.info['num_preferred']
        nmode = self.info['modes'][npref-1]
        modes = [x for x in self.modes if x['id'] == nmode]
        assert len(modes) == 1, 'There can only be one preferred mode.'
        return modes[0]

    @property
    def current_mode(self):
        modes = self._get_modes()
        try:
            mode_id = self.crtc.info['mode']
        except KeyError:
            return {}
        modes = [x for x in modes if x['id'] == mode_id]
        assert len(modes) == 1, 'There can only be one current mode.'
        return modes[0]

    def __repr__(self):
        cname = self.__class__.__name__
        return cname + '({})'.format(self.idx)


class Monitor(BaseMonitor):
    def __init__(self, index):
        """Index is the X11 index of the output"""
        self._id = index
        self._xout = X11Output(index)

    def _get_output_edid(self):
        return self._xout.edid

    def _dflt_resolution(self):
        d = self._xout.preferred_mode
        self._width_in_pixels, self._height_in_pixels = d['width'], d['height']

    @property
    def output_name(self):
        return self._xout.output_name

    @property
    def is_primary(self):
        xo = self._xout
        return xo.idx == xo.idx_primary

    @property
    def x11_output_id(self):
        return self._xout.idx

    @property
    def status(self):
        crtc = self._xout.crtc
        if crtc.idx == 0:
            return 'off'
        return 'on'

    @property
    def geometry(self):
        d = self._xout.crtc.info
        try:
            x, y, width, height = d['x'], d['y'], d['width'], d['height']
        except KeyError:
            x, y, width, height = 0, 0, 0, 0
        return Geometry(x, y, width, height)

    def __str__(self):
        sstr = super(Monitor, self).__str__()
        sstr += '\t->\t{}x{}'.format(self.width_in_pixels, self.height_in_pixels)
        return sstr


def get_monitors():
    "Return a Monitor instance for each connected computer monitor."
    return [Monitor(x) for x in get_connected_outputs()]

if __name__ == '__main__':
    monitors = get_monitors()
    # monitors = [Monitor(x) for x in get_connected_outputs()]
    for mon in monitors:
        print(mon)
