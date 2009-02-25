/*  cbr
 *  OracleLocationService.cpp
 *
 *  Copyright (c) 2009, Ewen Cheslack-Postava
 *  All rights reserved.
 *
 *  Redistribution and use in source and binary forms, with or without
 *  modification, are permitted provided that the following conditions are
 *  met:
 *  * Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *  * Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in
 *    the documentation and/or other materials provided with the
 *    distribution.
 *  * Neither the name of cbr nor the names of its contributors may
 *    be used to endorse or promote products derived from this software
 *    without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
 * IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
 * TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
 * PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER
 * OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
 * PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
 * LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
 * NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
 * SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#include "OracleLocationService.hpp"

namespace CBR {

void OracleLocationService::tick(const Time& t) {
    // FIXME we could maintain a heap of event times instead of scanning through this list every time
    for(LocationMap::iterator it = mLocations.begin(); it != mLocations.end(); it++) {
        LocationInfo& locinfo = it->second;
        if(locinfo.has_next && locinfo.next.updateTime() <= t) {
            locinfo.location = locinfo.next;
            const MotionVector3f* next = locinfo.path->nextUpdate(t);
            if (next == NULL)
                locinfo.has_next = false;
            else
                locinfo.next = *next;
        }
    }
}

MotionVector3f OracleLocationService::location(const UUID& uuid) {
    LocationMap::iterator it = mLocations.find(uuid);
    assert(it != mLocations.end());

    LocationInfo locinfo = it->second;
    return locinfo.location;
}

} // namespace CBR
