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
"""Message boxes and tooltips that show user or AI text without ever interpreting it as markup."""
import html

from PyQt5 import QtCore, QtWidgets


def message_box(parent, icon, title, text, buttons=QtWidgets.QMessageBox.Ok, default=QtWidgets.QMessageBox.NoButton):
    """
    Show a modal box with ``text`` as plain text and return the button pressed.

    The static ``QMessageBox`` helpers auto-detect rich text, so a cover title or a provider message such as
    ``<img src=http://...>`` would be drawn as markup; this builds the box and fixes the format instead.
    """
    box = QtWidgets.QMessageBox(icon, title, text, buttons, parent)
    box.setTextFormat(QtCore.Qt.PlainText)
    if default != QtWidgets.QMessageBox.NoButton:
        box.setDefaultButton(default)
    return box.exec()


def plain_tooltip(text):
    """
    ``text`` as a tooltip that shows exactly those characters. Qt has no plain mode for tooltips (it treats anything
    that might be markup as markup), so the text is escaped and wrapped in markup that keeps its line breaks.
    """
    return '<p style="white-space:pre">' + html.escape(text) + '</p>'
