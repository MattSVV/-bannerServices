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


class RepositoryError(Exception):
    """The cover store failed (I/O error, refused input...). The message is presentable to the user."""


class InvalidCoverId(RepositoryError, ValueError):
    """A cover id is not a safe identifier (path separators, ``..``, reserved names, bad length...)."""


class CoverNotFound(RepositoryError, KeyError):
    """No cover is stored under the requested id."""

    def __str__(self):
        return Exception.__str__(self)


class CoverCorrupt(RepositoryError):
    """A stored cover exists but cannot be read (broken JSON, unknown schema version, missing image)."""


class ExportExists(RepositoryError):
    """The export destination already exists and overwriting was not requested."""


class CoverRepository(ABC):
    """Stores covers (their data and rendered PNG) and finds them again."""

    @abstractmethod
    def save(self, cover, png_bytes):
        """
        Store ``cover`` and its PNG, replacing any cover with the same id. All-or-nothing: a failure leaves the
        previous state untouched.

        :raises InvalidCoverId: when ``cover.id`` is not a safe identifier.
        :raises RepositoryError: when ``png_bytes`` is not a PNG or the store cannot be written.
        """

    @abstractmethod
    def get(self, cover_id):
        """
        Return the ``Cover`` stored under ``cover_id``.

        :raises InvalidCoverId: / :raises CoverNotFound: / :raises CoverCorrupt:
        """

    @abstractmethod
    def list(self):
        """Return every readable cover, newest first. Unreadable entries are skipped with a logged warning."""

    @abstractmethod
    def delete(self, cover_id):
        """Remove a cover and its PNG. :raises CoverNotFound: when it does not exist."""

    @abstractmethod
    def export_png(self, cover_id, dest_path, overwrite=False):
        """
        Copy the cover's PNG to ``dest_path``.

        :raises ExportExists: when ``dest_path`` exists and ``overwrite`` is false.
        :raises RepositoryError: when the destination cannot be written.
        """

    @abstractmethod
    def png_path(self, cover_id):
        """
        Return the path of the stored PNG, for thumbnails and for adding it to a service. Treat it as read-only.

        :raises CoverNotFound: when there is no such cover.
        """


class SecretStoreError(Exception):
    """The secret store could not be read or written. The message is presentable and never contains a key."""


class SecretStore(ABC):
    """Keeps one API key per AI provider, apart from OpenLP's settings so exports and backups never contain them."""

    @abstractmethod
    def get_api_key(self, provider):
        """
        Return the stored key for ``provider``, or ``None`` when there is none or the store cannot be trusted
        (for example a file that other users can read). Never logs a key.

        :raises ValueError: for an unknown provider.
        """

    @abstractmethod
    def get_api_key_origin(self, provider):
        """
        Return the origin (see ``ai_config.origin_of``) the key of ``provider`` was entered for, or ``None`` when none
        was recorded (a key stored before origins existed, or a provider with a fixed address).
        """

    @abstractmethod
    def set_api_key(self, provider, key, origin=None):
        """
        Store ``key`` (surrounding whitespace is removed), replacing any previous one and its origin. ``origin`` is
        the server the key may be sent to; it is recorded for providers whose address the user can change.

        :raises ValueError: for an unknown provider or an unusable key.
        :raises SecretStoreError: when the key cannot be written.
        """

    @abstractmethod
    def delete_api_key(self, provider):
        """Forget the key of ``provider``. Deleting a key that is not there is not an error."""


class DesignError(Exception):
    """
    The AI design step failed (bad key, quota, timeout, unusable reply...). The message is presentable to the user
    and never contains an API key, a request header or the request body.
    """


class UnusableReply(DesignError):
    """The provider answered, but not with a usable design (not JSON, no template...). Worth one repair round."""


@dataclass(frozen=True)
class DesignRequest:
    """What a ``CoverDesigner`` is asked: a system prompt (the rules) and a user prompt (style hint and cover text)."""
    system_prompt: str
    user_prompt: str


@dataclass(frozen=True)
class DesignProposal:
    """The raw answer of a designer: untrusted HTML (a template with placeholders), an optional icon, a short note."""
    template_html: str
    icon_svg: str = None
    notes: str = ''


class CoverDesigner(ABC):
    """Asks an AI to design a cover template. Implementations talk to one provider and block until it answers."""

    @abstractmethod
    def design(self, request):
        """
        Send ``request`` and return the parsed ``DesignProposal``. The proposal is **untrusted**: callers must
        sanitise it before use. Blocks, so call it from a worker thread.

        :raises DesignError: for every failure, with a message that is safe to show.
        """

    def test_connection(self):
        """Check the key and model cheaply and return a message to show. :raises DesignError: when it fails."""
        raise DesignError('This provider cannot be tested.')
