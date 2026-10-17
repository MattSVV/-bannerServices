# -*- coding: utf-8 -*-

##########################################################################
# Portadas - sermon cover plugin for OpenLP                              #
# ---------------------------------------------------------------------- #
# Copyright (c) 2026 Portadas contributors                               #
# ---------------------------------------------------------------------- #
# This program is free software: you can redistribute it and/or modify   #
# it under the terms of the GNU General Public License as published by   #
# the Free Software Foundation, either version 3 of the License, or      #
# (at your option) any later version.                                    #
#                                                                        #
# This program is distributed in the hope that it will be useful,        #
# but WITHOUT ANY WARRANTY; without even the implied warranty of         #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
# GNU General Public License for more details.                           #
#                                                                        #
# You should have received a copy of the GNU General Public License      #
# along with this program.  If not, see <https://www.gnu.org/licenses/>. #
##########################################################################
"""Ports: the interfaces the application layer needs from the outside world. Adapters implement them."""
from abc import ABC, abstractmethod
from dataclasses import dataclass

DEFAULT_SIZE = (1920, 1080)


class RenderError(Exception):
    """A cover could not be rendered to an image (timeout, load failure, crashed render process...)."""


@dataclass(frozen=True)
class RenderResult:
    """
    The outcome of a render.

    :param png_bytes: the encoded PNG.
    :param overflow: placeholder names (``title_main``, ``subtitle``...) whose text does not fit its box, runs off
        the canvas or collides with another field. Empty when everything fits.
    """
    png_bytes: bytes
    overflow: tuple = ()


class CoverRenderer(ABC):
    """Turns a cover's final HTML into a PNG."""

    @abstractmethod
    def render(self, html, base_dir, size=DEFAULT_SIZE):
        """
        Render ``html`` and block until the image is ready.

        :param html: the complete (already sanitised and filled-in) HTML document.
        :param base_dir: directory that relative URLs in ``html`` resolve against; also the only extra directory the
            page may read files from.
        :param size: ``(width, height)`` of the image in pixels.
        :returns: a ``RenderResult``.
        :raises RenderError: when the render fails or times out.
        :raises ValueError: when ``size`` is not a sensible pair of positive integers.
        """

    @abstractmethod
    def render_async(self, html, base_dir, on_done, on_error, size=DEFAULT_SIZE):
        """
        Like ``render`` but returns immediately; exactly one of the callbacks runs later, on the calling thread's
        event loop: ``on_done(RenderResult)`` or ``on_error(RenderError)``.
        """
