Third-party code included in this repository
===========================================

The engine links against the Syzygy / Fathom tablebase probing code. That code
is not mine and is not covered by this project's LICENSE. Both files carry
their own MIT licence and their own copyright notices, which must stay
intact in any copy or redistribution.

MIT is GPL-compatible, so these files may be included in a GPL project.


tbprobe.c / tbprobe.h
---------------------

    (C) 2015 basil, all rights reserved

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the "Software"),
    to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense,
    and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included
    in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
    THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.

    https://github.com/basil00/DtNeglect


tbchess.c
---------

    Copyright (c) 2015 basil00
    Modifications Copyright (c) 2016-2020 by Jon Dart

    MIT licence, same terms as above. The notice is retained in the source
    file and must not be removed.

    https://github.com/jonddart/tbchess


Syzygy tablebases
----------------

The tablebase files themselves (.rtbw, .rtbz) are NOT part of this repository
and are NOT covered by any licence here. They are large binary data produced
by separate projects and are distributed under their own terms. See the
upstream projects before redistributing them.

This project only contains the code that reads them.
