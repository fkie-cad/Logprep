"""rstr - Generate random strings from regular expressions."""

# Copyright (c) 2011, Leapfrog Direct Response, LLC
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the Leapfrog Direct Response, LLC, including
#      its subsidiaries and affiliates nor the names of its
#      contributors, may be used to endorse or promote products derived
#      from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL LEAPFROG DIRECT
# RESPONSE, LLC, INCLUDING ITS SUBSIDIARIES AND AFFILIATES, BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN
# IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# source: https://github.com/leapfrogonline/rstr

from logprep.util.rstr.xeger import Xeger

Rstr = Xeger
_default_instance = Rstr()

rstr = _default_instance.rstr
xeger = _default_instance.xeger


# This allows convenience methods from rstr to be accessed at the package
# level, without requiring the user to instantiate an Rstr() object.
printable = _default_instance.printable
letters = _default_instance.letters
uppercase = _default_instance.uppercase
lowercase = _default_instance.lowercase
digits = _default_instance.digits
punctuation = _default_instance.punctuation
nondigits = _default_instance.nondigits
nonletters = _default_instance.nonletters
whitespace = _default_instance.whitespace
nonwhitespace = _default_instance.nonwhitespace
normal = _default_instance.normal
word = _default_instance.word
nonword = _default_instance.nonword
unambiguous = _default_instance.unambiguous
postalsafe = _default_instance.postalsafe
urlsafe = _default_instance.urlsafe
domainsafe = _default_instance.domainsafe
