#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test Network
------------

This module tests the basic functionality of a VLAN network.  Each test "runs"
on a VLAN with two nodes, node_1 and node_2, and each has a state machine.
"""

import unittest

from bacpypes.debugging import bacpypes_debugging, ModuleLogger

from bacpypes.pdu import Address, LocalBroadcast, PDU
from bacpypes.comm import bind
from bacpypes.vlan import Network, Node

from ..state_machine import ClientStateMachine, StateMachineGroup
from ..time_machine import reset_time_machine, run_time_machine

# some debugging
_debug = 0
_log = ModuleLogger(globals())


@bacpypes_debugging
class ZPDU():

    def __init__(self, cls=None, **kwargs):
        if _debug: ZPDU._debug("__init__ %r", kwargs)

        self.cls = cls
        self.kwargs = kwargs

    def __eq__(self, pdu):
        if _debug: ZPDU._debug("__eq__ %r", pdu)

        # match the object type if it was provided
        if self.cls is not None:
            if not isinstance(pdu, self.cls):
                if _debug: ZPDU._debug("    - wrong class")
                return False

        # match the attribute names and values
        for k, v in self.kwargs.items():
            if not hasattr(pdu, k):
                if _debug: ZPDU._debug("    - missing attribute: %r", k)
                return False
            if getattr(pdu, k) != v:
                if _debug: ZPDU._debug("    - %s value: %r", k, v)
                return False

        # nothing failed
        return True


@bacpypes_debugging
class TNetwork(StateMachineGroup):

    def __init__(self, node_count):
        if _debug: TNetwork._debug("__init__ %r", node_count)
        StateMachineGroup.__init__(self)

        self.vlan = Network()

        for i in range(node_count):
            node = Node(Address(i + 1), self.vlan)

            # bind a client state machine to the node
            csm = ClientStateMachine()
            bind(csm, node)

            # add it to this group
            self.append(csm)

    def __getitem__(self, n):
        if _debug: TNetwork._debug("__getitem__ %r", n)

        # return the state machine for node address <n>
        return self.state_machines[n - 1]

    def run(self, time_limit=60.0):
        if _debug: TNetwork._debug("run %r", time_limit)

        # reset the time machine
        reset_time_machine()
        if _debug: TNetwork._debug("    - time machine reset")

        # run the group
        super(TNetwork, self).run()

        # run it for some time
        run_time_machine(time_limit)
        if _debug: TNetwork._debug("    - time machine finished")

        # check for success
        all_success, some_failed = super(TNetwork, self).check_for_success()
        assert all_success


@bacpypes_debugging
class TestVLAN(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        if _debug: TestVLAN._debug("__init__ %r %r", args, kwargs)
        super(TestVLAN, self).__init__(*args, **kwargs)

    def test_idle(self):
        if _debug: TestVLAN._debug("test_idle")

        # two element network
        tnet = TNetwork(2)

        # make a send transition from start to success, run the machine
        tnet[1].start_state.success()
        tnet[2].start_state.success()

        # run the group
        tnet.run()

    def test_send_receive(self):
        if _debug: TestVLAN._debug("test_send_receive")

        # two element network
        tnet = TNetwork(2)

        # make a PDU from node 1 to node 2
        pdu = PDU(b'data',
            source=Address(1),
            destination=Address(2),
            )
        if _debug: TestVLAN._debug("    - pdu: %r", pdu)

        # make a send transition from start to success, run the machine
        tnet[1].start_state.send(pdu).success()
        tnet[2].start_state.receive(ZPDU(
            pduSource=Address(1),
            )).success()

        # run the group
        tnet.run()

    def test_broadcast(self):
        if _debug: TestVLAN._debug("test_broadcast")

        # three element network
        tnet = TNetwork(3)

        # make a broadcast PDU
        pdu = PDU(b'data',
            source=Address(1),
            destination=LocalBroadcast(),
            )
        if _debug: TestVLAN._debug("    - pdu: %r", pdu)

        # make a send transition from start to success, run the machine
        tnet[1].start_state.send(pdu).success()
        tnet[2].start_state.receive(ZPDU(
            pduSource=Address(1),
            )).success()
        tnet[3].start_state.receive(ZPDU(
            pduSource=Address(1),
            )).success()

        # run the group
        tnet.run()

    def test_spoof_fail(self):
        if _debug: TestVLAN._debug("test_spoof_fail")

        # two element network
        tnet = TNetwork(1)

        # make a unicast PDU with the wrong source
        pdu = PDU(b'data',
            source=Address(2),
            destination=Address(3),
            )

        # make a send transition from start to success, run the machine
        tnet[1].start_state.send(pdu).success()

        # run the group
        with self.assertRaises(RuntimeError):
            tnet.run()

    def test_spoof_pass(self):
        if _debug: TestVLAN._debug("test_spoof_pass")

        # one node network
        tnet = TNetwork(1)

        # reach into the network and enable spoofing for the node
        tnet.vlan.nodes[0].spoofing = True

        # make a unicast PDU from a fictitious node
        pdu = PDU(b'data',
            source=Address(3),
            destination=Address(1),
            )

        # make a send transition from start to success, run the machine
        tnet[1].start_state.send(pdu).receive(ZPDU(
            pduSource=Address(3),
            )).success()

        # run the group
        tnet.run()

    def test_promiscuous(self):
        if _debug: TestVLAN._debug("test_promiscuous")

        # three element network
        tnet = TNetwork(3)

        # reach into the network and enable promiscuous mode
        tnet.vlan.nodes[2].promiscuous = True

        # make a PDU from node 1 to node 2
        pdu = PDU(b'data',
            source=Address(1),
            destination=Address(2),
            )

        # make a send transition from start to success, run the machine
        tnet[1].start_state.send(pdu).success()
        tnet[2].start_state.receive(ZPDU(
            pduSource=Address(1),
            )).success()
        tnet[3].start_state.receive(ZPDU(
            pduDestination=Address(2),
            )).success()

        # run the group
        tnet.run()

