"""
This file is part of Ludolph: Zabbix API plugin
Copyright (C) 2015-2016 Erigones, s. r. o.

See the LICENSE file for copying permission.
"""
import logging
from datetime import datetime, timedelta

from ludolph_zabbix import __version__
from ludolph.utils import parse_loglevel
from ludolph.web import webhook, request, abort
from ludolph.cron import cronjob
from ludolph.command import CommandError, command
from ludolph.message import IncomingLudolphMessage, red, green
from ludolph.plugins.plugin import LudolphPlugin
from zabbix_api import ZabbixAPI, ZabbixAPIException, ZabbixAPIError

logger = logging.getLogger(__name__)


def get_last(array, pop_before=False):
    try:
        if pop_before:
            array.pop()
        return array[-1]
    except IndexError:
        return None


def event_status(value):
    value = int(value)

    if value == 0:
        return green('OK')
    elif value == 1:
        return red('PROBLEM')
    else:
        return 'UNKNOWN'


class Zapi(LudolphPlugin):
    """
    Zabbix API connector for LudolphBot.

    Zabbix >= 2.0.6 is required.
    https://www.zabbix.com/documentation/2.0/manual/appendix/api/api
    """
    __version__ = __version__
    _zapi = None
    TIMEOUT = 10
    DURATION_SUFFIXES = {
        's': 'seconds',
        'm': 'minutes',
        'h': 'hours',
        'd': 'days',
    }

    def __post_init__(self):
        """Log in to zabbix"""
        config = self.config

        # Initialize zapi and try to login
        # HTTP authentication?
        httpuser = config.get('httpuser', None)
        httppasswd = config.get('httppasswd', None)
        # Whether to verify HTTPS server certificate (requires zabbix-api-erigones >= 1.2.2)
        ssl_verify = self.get_boolean_value(config.get('ssl_verify', True))

        # noinspection PyTypeChecker
        self._zapi = ZabbixAPI(server=config['server'], user=httpuser, passwd=httppasswd, timeout=self.TIMEOUT,
                               log_level=parse_loglevel(config.get('loglevel', 'INFO')), ssl_verify=ssl_verify)

        # Login and save zabbix credentials
        try:
            logger.info('Zabbix API login')
            self._zapi.login(config['username'], config['password'], save=True)
        except ZabbixAPIException as e:
            logger.critical('Zabbix API login error (%s)', e)

    @staticmethod
    def _parse_datetime(value, param_name):
        """Parse %Y-%m-%d-%H-%M string into datetime object"""
        if value == 'now':
            return datetime.now()
        else:
            try:
                return datetime.strptime(value, '%Y-%m-%d-%H-%M')
            except ValueError:
                raise CommandError('Invalid parameter: **%s**. Date-time required! (format: YYYY-mm-dd-HH-MM)' %
                                   param_name)

    @classmethod
    def _parse_datime_or_duration(cls, value, param_name, start_time=None, end_time=None):
        """Parse duration string into timedelta object and return start or end datetime"""
        assert start_time or end_time

        try:
            if value.endswith(('s', 'm', 'h', 'd')):
                dtype = cls.DURATION_SUFFIXES[value[-1]]
                duration = timedelta(**{dtype: int(value[:-1])})
            else:
                duration = timedelta(minutes=int(value))

            if start_time:
                return start_time + duration  # return end time
            else:
                return end_time - duration  # return start time
        except ValueError:
            try:
                return cls._parse_datetime(value, param_name)
            except CommandError:
                if start_time:
                    duration_symbol = '+'
                else:
                    duration_symbol = '-'

                raise CommandError('Invalid parameter: **%s**. Duration or date-time required! (format: '
                                   '%s<duration{s|m|h|d}> or <YYYY-mm-dd-HH-MM>)' % (param_name, duration_symbol))

    def zapi(self, method, params=None):
        """
        Acts as a decorator for executing zabbix API commands and checking zabbix API errors.
        """
        # Was never logged in. Repair authentication settings and restart Ludolph.
        if not (self._zapi and self._zapi.logged_in):
            raise CommandError('Zabbix API not available')

        try:
            return self._zapi.call(method, params=params)
        except ZabbixAPIError as ex:  # API command/application problem
            raise CommandError('%(message)s %(code)s: %(data)s' % ex.error)
        except ZabbixAPIException as ex:
            raise CommandError('Zabbix API error (%s)' % ex)  # API connection/transport problem problem

    def _search_hosts(self, *host_strings):
        """Search zabbix hosts by multiple host search strings. Return dict mapping of host IDs to host names"""
        res = {}
        params = {
            'output': ['hostid', 'name'],
            'searchWildcardsEnabled': True,
            'searchByAny': True,
        }

        for host_str in host_strings:
            params['search'] = {'name': host_str}

            for host in self.zapi('host.get', params):
                res[host['hostid']] = host['name']

        return res

    def _search_groups(self, *group_strings):
        """Search zabbix host groups by multiple group search strings. Return dict mapping group IDs to group names"""
        res = {}
        params = {
            'output': ['groupid', 'name'],
            'searchWildcardsEnabled': True,
            'searchByAny': True,
        }

        for group_str in group_strings:
            params['search'] = {'name': group_str}

            for host in self.zapi('hostgroup.get', params):
                res[host['groupid']] = host['name']

        return res

    @webhook('/alert', methods=('POST',))
    def alert(self):
        """
        Process zabbix alert request and send xmpp message to user/room.
        """
        jid = request.forms.get('jid', None)

        if not jid:
            logger.warning('Missing JID in alert request')
            abort(400, 'Missing JID in alert request')

        if jid == self.xmpp.room:
            mtype = 'groupchat'
        else:
            mtype = request.forms.get('mtype', 'normal')

            if mtype not in IncomingLudolphMessage.types:
                logger.warning('Invalid message type (%s) in alert request', mtype)
                abort(400, 'Invalid message type in alert request')

        msg = request.forms.get('msg', '')
        logger.info('Sending monitoring alert to "%s"', jid)
        logger.debug('\twith body: "%s"', msg)
        self.xmpp.msg_send(jid, msg, mtype=mtype)

        return 'Message sent'

    # noinspection PyUnusedLocal
    @command
    def zabbix_version(self, msg):
        """
        Show version of Zabbix API.

        Usage: zabbix-version
        """
        try:
            return 'Zabbix API version: ' + self._zapi.api_version()
        except ZabbixAPIException as ex:
            CommandError('Zabbix API error (%s)' % ex)  # API connection/transport problem problem

    def _get_alerts(self, groupids=None, hostids=None, monitored=True, maintenance=False, skip_dependent=True,
                    expand_description=False, select_hosts=('hostid',), active_only=True, priority=None,
                    output=('triggerid', 'state', 'error', 'description', 'priority', 'lastchange'), **kwargs):
        """Return iterator of current zabbix triggers"""
        params = {
            'groupids': groupids,
            'hostids': hostids,
            'monitored': monitored,
            'maintenance': maintenance,
            'skipDependent': skip_dependent,
            'expandDescription': expand_description,
            'filter': {'priority': priority},
            'selectHosts': select_hosts,
            'selectLastEvent': 'extend',  # API_OUTPUT_EXTEND
            'output': output,
            'sortfield': 'lastchange',
            'sortorder': 'DESC',  # ZBX_SORT_DOWN
        }

        if active_only:  # Whether to show current active alerts only
            params['filter']['value'] = 1  # TRIGGER_VALUE_TRUE

        params.update(kwargs)

        # If trigger is lost (broken expression) we skip it
        return (trigger for trigger in self.zapi('trigger.get', params) if trigger['hosts'])

    def _get_alert_events(self, triggers, since=None, until=None):
        """Get all events related to triggers"""
        triggerids = [t['triggerid'] for t in triggers]
        events = {}
        params = {
            'triggerids': triggerids,
            'object': 0,  # 0 - trigger
            'source': 0,  # 0 - event created by a trigger
            'output': 'extend',
            'select_acknowledges': 'extend',
            'sortfield': ['clock', 'eventid'],
            'sortorder': 'DESC',
            'nodeids': 0,
        }

        if since and until:
            params['time_from'] = since
            params['time_till'] = until
        else:  # Max 15 days
            since = datetime.now() - timedelta(days=15)
            params['time_from'] = since.strftime('%s')

        for e in self.zapi('event.get', params):
            events.setdefault(e['objectid'], []).append(e)

        # Because of time limits, there may be some missing events for some trigger IDs
        missing_eventids = [t['lastEvent']['eventid'] for t in triggers if
                            t['lastEvent'] and t['triggerid'] not in events]

        if missing_eventids:
            for e in self.zapi('event.get', {'eventids': missing_eventids, 'source': 0, 'output': 'extend',
                                             'select_acknowledges': 'extend', 'nodeids': 0}):
                events.setdefault(e['objectid'], []).append(e)

        return events

    # noinspection PyUnusedLocal
    def _show_alerts(self, msg, since=None, until=None, last=None, display_notes=True, display_items=True,
                     hosts_or_groups=()):
        """Show current or historical events (alerts)"""
        _zapi = self._zapi
        zapi_server = _zapi.server
        get_datetime = _zapi.get_datetime
        out = []
        # Get triggers
        t_output = ('triggerid', 'state', 'error', 'url', 'expression', 'description', 'priority', 'type', 'comments',
                    'lastchange')
        t_hosts = ('hostid', 'name', 'maintenance_status', 'maintenance_type', 'maintenanceid')
        t_options = {'expand_description': True, 'output': t_output, 'select_hosts': t_hosts}

        if hosts_or_groups or last or (since and until):
            footer = []
        else:
            footer = ['%s/tr_status.php?groupid=0&hostid=0' % zapi_server]

        if display_items:
            t_options['selectItems'] = ('itemid', 'name')

        if hosts_or_groups:
            hosts = self._search_hosts(*hosts_or_groups)

            if hosts:
                t_options['hostids'] = list(hosts.keys())
                footer.append('Hosts: ' + ', '.join(hosts.values()))
            else:
                groups = self._search_groups(*hosts_or_groups)

                if groups:
                    t_options['groupids'] = list(groups.keys())
                    footer.append('Groups: ' + ', '.join(groups.values()))
                else:
                    raise CommandError('Invalid parameter: **host/group**. Existing host/group required!')

        if since and until:
            dt_until = self._parse_datetime(until, 'end')
            dt_since = self._parse_datime_or_duration(since, 'start', end_time=dt_until)
            t_options['lastChangeSince'] = since = dt_since.strftime('%s')
            t_options['lastChangeTill'] = until = dt_until.strftime('%s')
            t_options['active_only'] = False
            footer.append('Time period: %s - %s' % (_zapi.convert_datetime(dt_since), _zapi.convert_datetime(dt_until)))

        if last is not None:
            try:
                last = int(last)
            except ValueError:
                raise CommandError('Invalid parameter: **last**. Integer required!')
            else:
                t_options['limit'] = last
                t_options['active_only'] = False
                footer.append('Last: %d' % last)

        # Fetch triggers
        triggers = list(self._get_alerts(**t_options))
        triggers_hidden = 0

        # Get notes (dict) = related events + acknowledges
        events = self._get_alert_events(triggers, since=since, until=until)

        for trigger in triggers:
            related_events = events.get(trigger['triggerid'], ())

            # Skip triggers without any PROBLEM events. These events usually exist for newly created hosts,
            # but it will also skip triggers without PROBLEM events in historical view (Issue #6)
            if all(int(e['value']) == 0 for e in related_events):
                triggers_hidden += 1
                continue

            # Event
            last_event = trigger['lastEvent']
            if last_event:
                eventid = last_event['eventid']

                if int(last_event['value']):  # Problem or unknown state
                    eventid = '**%s**' % eventid

                # Ack
                if int(last_event['acknowledged']):
                    ack = '^^**ACK**^^'
                else:
                    ack = ''
            else:
                # WTF?
                eventid = '????'
                ack = ''

            # Host and hostname
            host = trigger['hosts'][0]
            hostname = host['name']
            if int(host['maintenance_status']):
                hostname += ' **++**'  # some kind of maintenance

            # Trigger description
            desc = str(trigger['description'])
            if trigger['error'] or int(trigger['state']):
                desc += ' **??**'  # some kind of trigger error

            # Priority
            prio = _zapi.get_severity(trigger['priority']).ljust(12)

            # Last change and age
            dt = get_datetime(trigger['lastchange'])
            age = '^^%s^^' % _zapi.get_age(dt)

            comments = ''
            if trigger['error']:
                comments += '\n\t\t^^**Error:** %s^^' % trigger['error']

            if trigger['comments']:
                comments += '\n\t\t^^Note: %s^^' % trigger['comments'].strip()

            if trigger['url']:
                comments += '\n\t\t^^URL: %s^^' % trigger['url'].strip()

            if display_items:
                # Link to latest data graph
                history_link = '[[' + zapi_server + '/history.php?action=showgraph&itemid=%(itemid)s|%(name)s]]'
                latest_data = '\n\t\tLatest data: %s' % (', '.join(history_link % i for i in trigger['items']))
            else:
                latest_data = ''

            trigger_events = []
            if display_notes:
                for e in related_events:
                    if int(e['acknowledged']):
                        e_ack = '^^**ACK**^^'
                    else:
                        e_ack = ''

                    trigger_events.append('\n\t\tEvent: %s\t%s\t^^**%s**^^\t%s' % (e['eventid'],
                                                                                   get_datetime(e['clock']),
                                                                                   event_status(e['value']),
                                                                                   e_ack))

                    for a in e['acknowledges']:
                        trigger_events.append('\n\t\t\t * __%s: %s__' % (_zapi.get_datetime(a['clock']), a['message']))

            if trigger_events:
                last_change = ''
            else:
                last_change = '\n\t\tLast change: %s' % dt

            out.append('%s\t%s\t%s\t%s\t%s\t%s%s%s%s%s\n' % (eventid, prio, hostname, desc, age, ack, comments,
                                                             latest_data, last_change, ''.join(trigger_events)))

        # footer
        stat = '\n**%d** issues are shown.' % (len(triggers) - triggers_hidden)
        if triggers_hidden:
            stat += '\n(%d issues are hidden)' % triggers_hidden
        out.append(stat)
        out.extend(footer)

        return '\n'.join(out)

    @command
    def alerts(self, msg, *args):
        """
        Show a list of current and/or previous zabbix alerts with events, notes and trigger items \
attached to each event ID. Alerts can be optionally filtered by host or group name and/or time period.

        Usage: alerts [host/group name] [last] [all|none]
        Usage: alerts [host/group name] [-duration{s|m|h|d}] [all|none]
        Usage: alerts [host/group name] <start date time Y-m-d-H-M> <end date time Y-m-d-H-M> [all|none]
        """
        notes = items = True
        start_time = end_time = last = None

        if args:
            args = list(args)
            cur = str(get_last(args, False)).strip()

            if cur == 'all':
                cur = get_last(args, True)
            elif cur == 'none':
                items = notes = False
                cur = get_last(args, True)

            if cur:
                if cur.isdigit():
                    last = args.pop()
                elif cur.startswith('-'):
                    end_time = 'now'
                    start_time = args.pop()[1:]
                elif len(args) > 1 and all(i.isdigit() for i in cur.split('-')):
                    end_time = args.pop()
                    start_time = args.pop()

        return self._show_alerts(msg, since=start_time, until=end_time, last=last, display_notes=notes,
                                 display_items=items, hosts_or_groups=args)

    @command
    def ack(self, msg, eventid, *eventids_or_note):
        """
        Acknowledge event(s) with optional note.

        Acknowledge event(s) by event ID.
        Usage: ack <event ID> [event ID2] [event ID3] ... [note]

        Acknowledge all unacknowledged event(s).
        Usage: ack all [note]
        """
        note = 'ack'

        if eventid == 'all':
            eventids = [t['lastEvent']['eventid'] for t in self._get_alerts(withLastEventUnacknowledged=True) if
                        t['lastEvent']]

            if not eventids:
                raise CommandError('No unacknowledged events found')

            if eventids_or_note:
                note = ' '.join(eventids_or_note)
        else:
            try:
                eventids = [int(eventid)]
            except ValueError:
                raise CommandError('Invalid parameter: **event ID**. Integer required!')

            for i, arg in enumerate(eventids_or_note):
                try:
                    eid = int(arg)
                except ValueError:
                    note = ' '.join(eventids_or_note[i:])
                    break
                else:
                    eventids.append(eid)

        message = '%s: %s' % (self.xmpp.get_jid(msg), note)

        res = self.zapi('event.acknowledge', {
            'eventids': eventids,
            'message': message,
        })

        return 'Event ID(s) **%s** acknowledged' % ','.join(map(str, res.get('eventids', ())))

    # noinspection PyUnusedLocal
    def _outage_del(self, msg, *mids):
        """
        Delete maintenance period(s) specified by maintenance ID.

        Usage: outage del <maintenance ID1> [maintenance ID2] [maintenance ID3] ...
        """
        try:
            mids = [int(i) for i in mids]
        except ValueError:
            raise CommandError('Invalid parameter: **maintenance ID**. Integer required!')

        self.zapi('maintenance.delete', mids)

        return 'Maintenance ID(s) **%s** deleted' % ','.join(map(str, mids))

    def _maintenance_add(self, jid, since, till, *hosts_or_groups):
        """Create maintenance period in zabbix"""
        period = till - since
        since = since.strftime('%s')
        till = till.strftime('%s')

        options = {
            'active_since': since,
            'active_till': till,
            'maintenance_type': 0,  # with data collection
            'timeperiods': [{
                'timeperiod_type': 0,  # one time only
                'start_date': since,
                'period': period.seconds,
            }],
        }

        # Get hosts
        hosts = self._search_hosts(*hosts_or_groups)

        if hosts:
            options['hostids'] = list(hosts.keys())
            desc = 'hosts: ' + ', '.join(hosts.values())
        else:
            # Get groups
            groups = self._search_groups(*hosts_or_groups)

            if groups:
                options['groupids'] = list(groups.keys())
                desc = 'groups: ' + ', '.join(groups.values())
            else:
                raise CommandError('Invalid parameter: **host/group**. Existing host/group required!')

        options['name'] = ('Maintenance %s by %s' % (since, jid))[:128]
        options['description'] = desc

        # Create maintenance period
        res = self.zapi('maintenance.create', options)

        return 'Added maintenance ID **%s** for %s' % (res['maintenanceids'][0], desc)

    def _outage_add(self, msg, start, end_or_duration, *hosts_or_groups):
        """
        Set maintenance period for specified host and time.
        """
        if not (start and end_or_duration and hosts_or_groups):
            raise CommandError('Parameter(s) required!')

        dt_start = self._parse_datetime(start, 'start')
        dt_end = self._parse_datime_or_duration(end_or_duration, 'end', start_time=dt_start)

        return self._maintenance_add(self.xmpp.get_jid(msg), dt_start, dt_end, *hosts_or_groups)

    # noinspection PyUnusedLocal
    def _outage_list(self, msg):
        """
        Show current maintenance periods.

        Usage: outage
        """
        out = []
        # Display list of maintenances
        maintenances = self.zapi('maintenance.get', {
            'output': 'extend',
            'sortfield': ['maintenanceid', 'name'],
            'sortorder': 'ASC',
        })

        for i in maintenances:
            if i['description']:
                desc = '\n\t^^%s^^' % i['description']
            else:
                desc = ''

            since = self._zapi.timestamp_to_datetime(i['active_since'])
            until = self._zapi.timestamp_to_datetime(i['active_till'])
            out.append('**%s**\t%s - %s\t__%s__%s\n' % (i['maintenanceid'], since, until, i['name'], desc))

        out.append('\n**%d** maintenances are shown.\n%s' % (len(maintenances),
                                                             self._zapi.server + '/maintenance.php?groupid=0'))

        return '\n'.join(out)

    @command
    def outage(self, msg, *args):
        """
        Show, create or delete maintenance periods.

        Show all maintenance periods.
        Usage: outage

        Set maintenance period for specified host and time.
        Usage: outage add <host1/group1 name> [host2/group2 name] ... +<duration{s|m|h|d}>
        Usage: outage add <host1/group1 name> [host2/group2 name] ... <start date time Y-m-d-H-M> \
<end date time Y-m-d-H-M>

        Delete maintenance period specified by maintenance ID.
        Usage: outage del <maintenance ID>
        """
        if len(args) > 1:
            action = args[0]

            if action == 'add':
                last_param = str(args[-1])

                if last_param.startswith('+'):
                    start_date = 'now'
                    end_date = last_param[1:]
                    hosts_or_groups = args[1:-1]
                else:
                    start_date = args[-2]
                    end_date = last_param
                    hosts_or_groups = args[1:-2]

                return self._outage_add(msg, start_date, end_date, *hosts_or_groups)
            elif action == 'del':
                return self._outage_del(msg, *args[1:])
            else:
                raise CommandError('Invalid action!')

        return self._outage_list(msg)

    @cronjob(minute=range(0, 60, 5))
    def maintenance(self):
        """
        Cron job for cleaning outdated outages and informing about incoming outage end.
        """
        maintenances = self.zapi('maintenance.get', {
            'output': 'extend',
            'sortfield': ['maintenanceid', 'name'],
            'sortorder': 'ASC',
        })
        now = datetime.now()
        in5 = now + timedelta(minutes=5)

        for i in maintenances:
            until = self._zapi.get_datetime(i['active_till'])
            mid = i['maintenanceid']
            name = i['name']
            desc = i['description'] or ''

            if until < now:
                logger.info('Deleting maintenance %s (%s)', mid, name)
                self.zapi('maintenance.delete', [mid])
                msg = 'Maintenance ID **%s** ^^(%s)^^ deleted' % (mid, desc)
            elif until < in5:
                logger.info('Sending notification about maintenance %s (%s) end', mid, name)
                msg = 'Maintenance ID **%s** ^^(%s)^^ is going to end %s' % (mid, desc,
                                                                             until.strftime('on %Y-%m-%d at %H:%M:%S'))
            else:
                continue

            jid = name.split()[-1]

            if '@' in jid:
                self.xmpp.msg_send(jid.strip(), msg)
            else:
                logging.warning('Missing JID in maintenance %s (%s). Broadcasting to all users..."', mid, name)
                self.xmpp.msg_broadcast(msg)

    # noinspection PyUnusedLocal
    @command
    def hosts(self, msg, hoststr=None):
        """
        Show a list of hosts.

        Usage: hosts [host name search string]
        """
        out = []
        params = {
            'output': ['hostid', 'name', 'available', 'maintenance_status', 'status'],
            'selectInventory': 1,  # All inventory items
            'sortfield': ['name', 'hostid'],
            'sortorder': 'ASC',
            'searchWildcardsEnabled': True,
            'searchByAny': True,
        }

        if hoststr:
            params['search'] = {'name': hoststr}

        # Get hosts
        hosts = self.zapi('host.get', params)

        for host in hosts:
            if int(host['maintenance_status']):
                host['name'] += ' **++**'  # some kind of maintenance

            if int(host['status']):
                status = 'Not monitored'
            else:
                status = 'Monitored'

            ae = int(host['available'])
            available = 'Z'
            if ae == 1:
                available = green('Z')
            elif ae == 2:
                available = red('Z')

            latest_data = '[[%s/latest.php?hostid=%s|Latest data]]' % (self._zapi.server, host['hostid'])

            _inventory = []
            if host['inventory']:
                for key, val in host['inventory'].items():
                    if val and key not in ('inventory_mode', 'hostid'):
                        _inventory.append('**%s**: %s' % (key, val))

            if _inventory:
                inventory = '\n\t\t^^%s^^' % str(', '.join(_inventory)).strip()
            else:
                inventory = ''

            out.append('**%s**\t%s\t%s\t%s\t%s%s' % (host['hostid'], host['name'], status,
                                                     available, latest_data, inventory))

        out.append('\n**%d** hosts are shown.\n%s/hosts.php?groupid=0' % (len(hosts), self._zapi.server))

        return '\n'.join(out)

    # noinspection PyUnusedLocal
    @command
    def groups(self, msg, groupstr=None):
        """
        Show a list of host groups.

        Usage: groups [group name search string]
        """
        out = []
        params = {
            'output': ['groupid', 'name'],
            'selectHosts': ['hostid', 'name'],
            'sortfield': ['name', 'groupid'],
            'sortorder': 'ASC',
            'searchWildcardsEnabled': True,
            'searchByAny': True,
        }

        if groupstr:
            params['search'] = {'name': groupstr}

        # Get groups
        groups = self.zapi('hostgroup.get', params)

        for group in groups:
            _hosts = ['**%s**: %s' % (h['hostid'], h['name']) for h in group['hosts'] if h]
            hosts = '\n\t\t^^%s ^^' % ', '.join(_hosts)
            out.append('**%s**\t%s%s' % (group['groupid'], group['name'], hosts))

        out.append('\n**%d** hostgroups are shown.\n%s/hostgroups.php' % (len(groups), self._zapi.server))

        return '\n'.join(out)
