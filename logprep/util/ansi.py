# Copyright (c) 2010 Jonathan Hartley
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:

# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.

# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.

# * Neither the name of the copyright holders, nor those of its contributors
#   may be used to endorse or promote products derived from this software without
#   specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
This module generates ANSI character codes to printing colors to terminals.
See: http://en.wikipedia.org/wiki/ANSI_escape_code
This module contains only a subset of the original colorama library. Additional codes can be added in this module from
https://github.com/tartley/colorama/blob/master/colorama/ansi.py.
"""

from enum import StrEnum

CSI = "\033["
OSC = "\033]"
BEL = "\a"


def _code_to_chars(code):
    return CSI + str(code) + "m"


class ForegroundColor(StrEnum):
    """
    Text foreground color codes for terminal display.
    """

    BLACK = _code_to_chars(30)
    RED = _code_to_chars(31)
    GREEN = _code_to_chars(32)
    YELLOW = _code_to_chars(33)
    BLUE = _code_to_chars(34)
    MAGENTA = _code_to_chars(35)
    CYAN = _code_to_chars(36)
    WHITE = _code_to_chars(37)
    RESET = _code_to_chars(39)


class BackgroundColor(StrEnum):
    """
    Text background color codes for terminal display.
    """

    BLACK = _code_to_chars(40)
    YELLOW = _code_to_chars(43)
    MAGENTA = _code_to_chars(45)
    CYAN = _code_to_chars(46)
    WHITE = _code_to_chars(47)
    RESET = _code_to_chars(49)


def color_print_line(back: BackgroundColor | None, fore: ForegroundColor | None, message: str):
    """Print string with colors and reset the color afterwards."""
    color = ""
    if back:
        color += back
    if fore:
        color += fore

    print(color + message + ForegroundColor.RESET + BackgroundColor.RESET)


def color_print_title(background: BackgroundColor, message: str):
    """Print dashed title line with black foreground colour and reset the color afterwards."""
    message = f"------ {message} ------"
    color_print_line(background, ForegroundColor.BLACK, message)


def print_fcolor(fore: ForegroundColor, message: str):
    """Print string with colored font and reset the color afterwards."""
    color_print_line(None, fore, message)
