# -*- coding: utf-8 -*-

#    Copyright (C) 2014 Yahoo! Inc. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from automaton import exceptions as automaton_exceptions
from automaton import machines
import six

"""State machine modelling.

This is being used in the implementation of:

http://specs.openstack.org/openstack/ironic-specs/specs/kilo/new-ironic-state-machine.html
"""


from ironic.common import exception as excp
from ironic.common.i18n import _


def _translate_excp(func):
    """Decorator to translate automaton exceptions into ironic exceptions."""

    @six.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (automaton_exceptions.InvalidState,
                automaton_exceptions.NotInitialized,
                automaton_exceptions.FrozenMachine,
                automaton_exceptions.NotFound) as e:
            raise excp.InvalidState(six.text_type(e))
        except automaton_exceptions.Duplicate as e:
            raise excp.Duplicate(six.text_type(e))

    return wrapper


class FSM(machines.FiniteMachine):
    """An ironic state-machine class with some ironic specific additions."""

    def __init__(self):
        super(FSM, self).__init__()
        self._target_state = None

    # For now make these raise ironic state machine exceptions until
    # a later period where these should(?) be using the raised automaton
    # exceptions directly.

    add_transition = _translate_excp(machines.FiniteMachine.add_transition)

    process_event = _translate_excp(machines.FiniteMachine.process_event)

    @property
    def target_state(self):
        return self._target_state

    @_translate_excp
    def add_state(self, state, on_enter=None, on_exit=None,
                  target=None, terminal=None, stable=False):
        """Adds a given state to the state machine.

        :param stable: Use this to specify that this state is a stable/passive
                       state. A state must have been previously defined as
                       'stable' before it can be used as a 'target'
        :param target: The target state for 'state' to go to.  Before a state
                       can be used as a target it must have been previously
                       added and specified as 'stable'

        Further arguments are interpreted as for parent method ``add_state``.
        """
        if target is not None:
            if target not in self._states:
                raise excp.InvalidState(
                    _("Target state '%s' does not exist") % target)
            if not self._states[target]['stable']:
                raise excp.InvalidState(
                    _("Target state '%s' is not a 'stable' state") % target)
        super(FSM, self).add_state(state, terminal=terminal,
                                   on_enter=on_enter, on_exit=on_exit)
        self._states[state].update({
            'stable': stable,
            'target': target,
        })

    def _post_process_event(self, event, result):
        # Clear '_target_state' if we've reached it
        if (self._target_state is not None and
                self._target_state == self._current.name):
            self._target_state = None
        # If new state has a different target, update the '_target_state'
        if self._states[self._current.name]['target'] is not None:
            self._target_state = self._states[self._current.name]['target']

    @_translate_excp
    def initialize(self, start_state=None):
        super(FSM, self).initialize(start_state=start_state)
        current_state = self._current.name
        self._target_state = self._states[current_state]['target']
