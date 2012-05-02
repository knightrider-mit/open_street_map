#!/usr/bin/python
# Software License Agreement (BSD License)
#
# Copyright (C) 2012, Jack O'Quin
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of the author nor of other contributors may be
#    used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Revision $Id$

"""
Create road network messages for geographic information maps.
"""

from __future__ import print_function

PKG_NAME = 'road_network'
import roslib; roslib.load_manifest(PKG_NAME)
import rospy

import sys
import itertools
import geodesy.utm

from osm_cartography import geo_map     # :todo: move to geodesy??
#from road_network.geo_graph import *

from geographic_msgs.msg import BoundingBox
from geographic_msgs.msg import RouteNetwork
from geographic_msgs.msg import RouteSegment
from geographic_msgs.msg import UniqueID
from geographic_msgs.srv import GetGeographicMap

# dynamic parameter reconfiguration
from dynamic_reconfigure.server import Server as ReconfigureServer
import road_network.cfg.RoadNetworkConfig as Config

class RoadNetNode():

    def __init__(self):
        """ROS node to publish the road network graph for a GeographicMap.
        """
        rospy.init_node('road_network')

        # advertise visualization marker topic
        self.pub = rospy.Publisher('route_network',
                                   RouteNetwork, latch=True)
        self.msg = None
        rospy.wait_for_service('get_geographic_map')
        self.get_map = rospy.ServiceProxy('get_geographic_map',
                                          GetGeographicMap)

        # register dynamic reconfigure callback, which runs immediately
        self.reconf_server = ReconfigureServer(Config, self.reconfigure)

    def build_graph(self, msg):
        """Build RouteNetwork graph for a GeographicMap message.

        :post: self.msg = RouteNetwork message
        """
        self.geo_map = geo_map.GeoMap(msg)
        self.map_features = geo_map.GeoMapFeatures(self.geo_map)
        self.map_points = geo_map.GeoMapPoints(self.geo_map)
        self.msg = RouteNetwork(bounds = msg.bounds)

        # process each feature tagged as a road
        for feature in itertools.ifilter(self.is_road, self.map_features):
            oneway = self.is_oneway(feature) # :todo: add to GeoMap class??
            start = None
            for mbr in feature.components:
                pt = self.map_points.get(mbr.uuid)
                if pt is not None:      # known way point?
                    self.msg.points.append(pt)
                    end = UniqueID(uuid = mbr.uuid)
                    if start is not None:
                        self.msg.segments.append(RouteSegment(start = start,
                                                              end = end))
                        if not oneway:
                            self.msg.segments.append(RouteSegment(start = end,
                                                                  end = start))
                    start = end

    def is_oneway(self, feat):
        ':returns: True if feat is one way.'
        return False            # :todo: check the tags

    def is_road(self, feat):
        ':returns: True if feat is drivable.'
        return geo_map.match_tags(feat, geo_map.road_tags)
    
    def reconfigure(self, config, level):
        """Dynamic reconfigure callback.

        :param config: New configuration.
        :param level:  0x00000001 bit set if URL changed (ignored).

        :returns: New config if valid, old one otherwise. That updates
                  the dynamic reconfigure GUI window.
        """
        rospy.loginfo('Map URL: ' + str(config.map_url))

        try:
            resp = self.get_map(config.map_url, BoundingBox())
        except rospy.ServiceException as e:
            rospy.logerr("Service call failed:", str(e))
            # ignore new config, it failed
        else:                           # get_map returned
            if resp.success:
                self.build_graph(resp.map)
                self.config = config    # save new URL
                #print(str(self.msg))
                # publish visualization markers (on a latched topic)
                self.pub.publish(self.msg)
            else:
                print('get_geographic_map failed, status:', str(resp.status))

        return self.config
    
def main():
    node_class = RoadNetNode()
    try:
        rospy.spin()
    except rospy.ROSInterruptException: pass

if __name__ == '__main__':
    # run main function and exit
    sys.exit(main())