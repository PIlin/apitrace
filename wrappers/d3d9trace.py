##########################################################################
#
# Copyright 2008-2009 VMware, Inc.
# All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
##########################################################################/


from dlltrace import DllTracer
from specs.stdapi import API, Pointer, ObjPointer
from specs.d3d9 import d3d9, D3DSHADER9, IDirect3DSwapChain9Ex

import specs.d3d9dxva2


class D3D9Tracer(DllTracer):

    def serializeArgValue(self, function, arg):
        # Dump shaders as strings
        if arg.type is D3DSHADER9:
            print '    DumpShader(trace::localWriter, %s);' % (arg.name)
            return

        DllTracer.serializeArgValue(self, function, arg)

    def wrapArg(self, function, arg):
        # Correctly handle the wrapping of IDirect3DSwapChain9Ex objects
        if function.name in ('GetSwapChain', 'CreateAdditionalSwapChain') \
           and self.interface.name == 'IDirect3DDevice9Ex' \
           and arg.name == 'pSwapChain':
            self.wrapValue(Pointer(ObjPointer(IDirect3DSwapChain9Ex)), '((IDirect3DSwapChain9Ex**)pSwapChain)')
            return

        DllTracer.wrapArg(self, function, arg)

    def enumWrapperInterfaceVariables(self, interface):
        variables = DllTracer.enumWrapperInterfaceVariables(self, interface)
        
        # Add additional members to track locks
        if interface.getMethodByName('Lock') is not None or \
           interface.getMethodByName('LockRect') is not None or \
           interface.getMethodByName('LockBox') is not None:
            if interface.name in ['IDirect3DTexture9']:
                variables += [
                    ('std::map<UINT, std::pair<size_t, VOID *> >', '_MappedData', 'std::map<UINT, std::pair<size_t, VOID *> >()'),
                ]
            else:
                variables += [
                    ('size_t', '_MappedSize', '0'),
                    ('VOID *', 'm_pbData', '0'),
                ]

        return variables

    def implementWrapperInterfaceMethodBody(self, interface, base, method):
        if method.name in ('Unlock', 'UnlockRect', 'UnlockBox'):
            if interface.name in ['IDirect3DTexture9']:
                print '    std::map<UINT, std::pair<size_t, VOID *> >::iterator it = _MappedData.find(Level);'
                print '    if (it != _MappedData.end()) {'
                self.emit_memcpy('(LPBYTE)it->second.second', 'it->second.first')
                print '        _MappedData.erase(it);'
                print '    }'
            else:
                print '    if (_MappedSize && m_pbData) {'
                self.emit_memcpy('(LPBYTE)m_pbData', '_MappedSize')
                print '    }'

        DllTracer.implementWrapperInterfaceMethodBody(self, interface, base, method)

        if method.name in ('Lock', 'LockRect', 'LockBox'):
            if interface.name in ['IDirect3DTexture9']:
                print '    if (SUCCEEDED(_result) && !(Flags & D3DLOCK_READONLY)) {'
                print '        size_t mappedSize;'
                print '        VOID * pbData;'
                print '        _getMapInfo(_this, %s, pbData, mappedSize);' % ', '.join(method.argNames()[:-1])
                print '        _MappedData[Level] = std::make_pair(mappedSize, pbData);'
                print '    } else {'
                print '        _MappedData.erase(Level);'
                print '    }'
            else:
                # FIXME: handle recursive locks
                print '    if (SUCCEEDED(_result) && !(Flags & D3DLOCK_READONLY)) {'
                print '        _getMapInfo(_this, %s, m_pbData, _MappedSize);' % ', '.join(method.argNames()[:-1])
                print '    } else {'
                print '        m_pbData = NULL;'
                print '        _MappedSize = 0;'
                print '    }'


if __name__ == '__main__':
    print '#define INITGUID'
    print
    print '#include "trace_writer_local.hpp"'
    print '#include "os.hpp"'
    print
    print '#include "d3d9imports.hpp"'
    print '#include "d3d9size.hpp"'
    print '#include "d3d9shader.hpp"'
    print '#include "dxvaint.h"'
    print

    api = API()
    api.addModule(d3d9)
    tracer = D3D9Tracer()
    tracer.traceApi(api)
