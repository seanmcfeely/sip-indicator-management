
import configparser
import csv
import datetime
import getpass
import json
import logging, logging.config
import os
import re
import sys
import pymysql
import time

from tqdm import tqdm

from collections import Counter
from dateutil.parser import parse

import pysip

from indicator_management.config import CONFIG, HOME_PATH

class IndicatorManager:
    def __init__(self, config: configparser.ConfigParser=CONFIG, dev=False):
        self.prod = not dev

        self.indicators = None
        # Save the config file.
        self.config = config

        # Start logging.
        self.logger = logging.getLogger('indicator_management.IndicatorManager')

        # Connect to SIP.
        if self.prod:
            verify = self.config['sip_prod'].getboolean('verify_ssl')
            if verify:
                if os.path.exists(self.config['sip_prod']['ca_bundle']):
                    verify=self.config['sip_prod']['ca_bundle']
            self.sip = pysip.Client(self.config['sip_prod']['host'], self.config['sip_prod']['api_key'], verify=verify)
        else:
            verify = self.config['sip_dev'].getboolean('verify_ssl')
            if verify:
                if os.path.exists(self.config['sip_dev']['ca_bundle']):
                    verify=self.config['sip_dev']['ca_bundle']
            self.sip = pysip.Client(self.config['sip_dev']['host'], self.config['sip_dev']['api_key'], verify=verify)

        self.logger.info('self.prod = {}'.format(self.prod))

        self._ace_db_cursor = None

    def connect_to_ace(self):
        if isinstance(self._ace_db_cursor, pymysql.cursors.DictCursor):
            self.logger.debug('Returning existing connection to ACE.')
            return self._ace_db_cursor

        ace_host = self.config['ace_db']['host']
        ace_port = self.config['ace_db']['port']
        ace_user = self.config['ace_db']['user']
        ace_db   = self.config['ace_db']['db']
        ace_pass = self.config['ace_db']['password']
        #ace_pass = getpass.getpass(prompt='ACE database password for user "{}": '.format(ace_user))

        self.logger.debug('Connecting to ACE database {}@{}:{}'.format(ace_user, ace_host, ace_port))
        ssl_settings = {'ca': self.config['ace_db']['ca_bundle']}
        ace_db = pymysql.connect(host=ace_host, port=int(ace_port), user=ace_user, password=ace_pass, database=ace_db, ssl=ssl_settings)
        self._ace_db_cursor = ace_db.cursor(pymysql.cursors.DictCursor)
        return self._ace_db_cursor

    def disable_indicator(self, indicator):
        data = {'status': 'Informational'}
        self.sip.put('/api/indicators/{}'.format(indicator['id']), data)
        self.logger.debug('Disabled indicator "{}" ({})'.format(indicator['value'], indicator['id']))
        return True

    def enable_indicator(self, indicator):
        data = {'status': 'New'}
        self.sip.put('/api/indicators/{}'.format(indicator['id']), data)
        self.logger.debug('Enabling indicator "{}" ({})'.format(indicator['value'], indicator['id']))
        return True

    def create_result_recording_dir(self, dir_name):
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
        return dir_name

    def record_indicator_tune(self, recording_dir, indicator):
        fname = f"{indicator['id']}.json"
        fpath = os.path.join(recording_dir, fname)
        with open(fpath, 'w') as fp:
            fp.write(json.dumps(indicator))
        if os.path.exists(fpath):
            self.logger.debug('Wrote indicator "{}" to {}'.format(indicator['id'], fpath))
            return fpath
        return False

    def find_indicators_to_turn_off(self, tune_instructions: configparser.SectionProxy, dry_run=True, recording_dir=None, print_scope_only=False):
        """Find indicators to turn off based on tuning instructions.

        Only turn off indicators if dry_run is True.

        If recording_dir points to a directory that exists, record the indicators we turn off there.
        """
        # Only consider indicators that are at least this old.
        tuning_days = tune_instructions.getint('days') if 'days' in tune_instructions else self.config['default_tune_settings'].getint('days', 90)
        min_age = datetime.datetime.now() - datetime.timedelta(days=tuning_days)

        # Start building the sip query.
        query = f"/api/indicators?&status=Analyzed&modified_before={min_age}"

        # Only consider these indicator types.
        bad_indicator_types = tune_instructions['indicator_types'].split(',') if tune_instructions.get('indicator_types') else []
        if not bad_indicator_types:
            # tune instructions didn't specify any indicator types, so use all of them.
            bad_indicator_types = [i['value'] for i in self.sip.get('/api/indicators/type')]
        query += '&types=' + ','.join(bad_indicator_types)
        #query += f"&types={','.join(bad_indicator_types)}"

        # Only consider these SIP intel sources.
        sources_in_scope = tune_instructions['sources'].split(',') if tune_instructions.get('sources') else []
        #if not sources_in_scope:
        #    sources_in_scope = [s['value'] for s in self.sip.get('/api/intel/source')]
        if sources_in_scope:
            query += '&sources=[OR]' + ','.join(sources_in_scope)

        not_sources_in_scope = tune_instructions['not_sources'].split(',') if tune_instructions.get('not_sources') else []
        if not_sources_in_scope:
            query += '&not_sources=' + ','.join(not_sources_in_scope)

        # Do not tune intel from these analysts.
        good_analysts = tune_instructions['good_analysts'].split(',') if tune_instructions.get('good_analysts') else []
        query += '&not_users=' + ','.join(good_analysts)

        # Do not tune indicators with these tags. 
        good_tags = tune_instructions['good_tags'].split(',') if tune_instructions.get('good_tags') else []
        query += '&not_tags=' + ','.join(good_tags)

        # Search SIP for the indicators in scope.
        self.logger.info(f"querying sip for indicators matching: {query}")
        matching_indicators = self.sip.get(query)
        self.logger.info(f"got {len(matching_indicators)} matching indicators")

        if print_scope_only:
            print(f"\nAn execution of this tuning config would have {len(matching_indicators)} indicators in scope for being potentially turned off.")
            print()
            return True

        # Only consider these ACE alert dispositions.
        bad_dispositions = tune_instructions['dispositions'].split(',') if tune_instructions.get('dispositions') else []
        if not bad_dispositions:
            bad_dispositions = self.config['default_tune_settings']['dispositions'].split(',')

        # Search ACE for alerts from each indicator.
        ace_cur = self.connect_to_ace()
        bad_indicators = []
        for indicator in matching_indicators:
            good = True
            indicator_id = indicator['id']
            indicator_id_string = 'sip:{}'.format(indicator_id)
            #indicator_alert_cutoff_time = indicator_created + datetime.timedelta(days=30)
            indicator_alert_cutoff_time = min_age

            # Query the ACE database for this indicator ID.
            ace_cur.execute("""SELECT * FROM
                                   observables o JOIN observable_mapping om ON o.id = om.observable_id
                                   JOIN alerts a ON a.id = om.alert_id
                               WHERE
                                   o.type = 'indicator' AND o.value = '""" + indicator_id_string + "' AND a.alert_type != 'faqueue'")

            # Get all of the results.
            results = ace_cur.fetchall()

            # If we have alerted on this indicator...
            if results:

                # Collect all of the dispositions for this indicator.
                dispositions = []

                for alert in results:

                    # Skip this alert if it's from FA Queue.
                    if 'FA Queue' in alert['description']:
                        continue

                    # Skip this alert if it's older than the cutoff time.
                    alert_created_time = alert['insert_date']
                    if alert_created_time < indicator_alert_cutoff_time:
                        continue
                    
                    dispositions.append(alert['disposition'])

                # Mark this as a bad indicator if all of the alerts were bad dispositions.
                if dispositions:
                    if all(dispo in bad_dispositions for dispo in dispositions):
                        bad_indicators.append(indicator)
                        self.logger.info("FP/RECON: " + " | ".join([indicator_id_string, indicator["type"], indicator["value"]]))
                        good = False
                else:
                    bad_indicators.append(indicator)
                    self.logger.info("NO MATCHING ALERTS AFTER {}: ".format(indicator_alert_cutoff_time) + " | ".join([indicator_id_string, indicator["type"], indicator["value"]]))
                    good = False
            # Since we didn't alert on it, mark it as bad.
            else:
                bad_indicators.append(indicator)
                self.logger.info("NO ALERTS: " + " | ".join([indicator_id_string, indicator["type"], indicator["value"]]))
                good = False

            if good:
                self.logger.info("GOOD INDICATOR: " + " | ".join([indicator_id_string, indicator["type"], indicator["value"]]))

        self.logger.info('Found {} Analyzed indicators'.format(self.sip.get('/api/indicators?status=Analyzed&count')))
        self.logger.info('{} of them are older than {}'.format(len(matching_indicators), str(min_age)))
        self.logger.info('{} of those were either FP/RECON/NO ALERTS'.format(len(bad_indicators), str(min_age)))

        if dry_run:
            self.logger.info(f"Dry run, not turning off these indicators.")
            return True

        self.logger.info("Turning off these indicators.")
        for indicator in bad_indicators:
            if os.path.exists(recording_dir):
                if not self.record_indicator_tune(recording_dir, indicator):
                    self.logger.warning(f'Failed to write indicator "{indicator["id"]}.json" to {recording_dir}. Not turning off.')
                    continue
            self.disable_indicator(indicator)

        return True

    def turn_off_indicators_according_to_tune_instructions(self, dry_run=True, record_changes=True, print_scope_only=False):
        """Turn off indicators according to the configured tuning instructions.
        """
        tune_sections = [section for section in self.config.sections() if section.startswith('tune_') and self.config[section].getboolean('enabled')]
        if not tune_sections:
            self.logger.info("No tuning instructions found.")
            return True

        for section in tune_sections:
            recording_dir = None
            if record_changes:
                recording_dir = os.path.join(HOME_PATH, "var", "records", f"{datetime.datetime.now().date()}", section)
                self.create_result_recording_dir(recording_dir) 

            self.logger.info(f"Turning off indicators according to {section}")
            self.find_indicators_to_turn_off(self.config[section], dry_run, recording_dir=recording_dir, print_scope_only=print_scope_only)

        return True

    def reset_in_progress(self):
        # Get the initial list of In Progress indicators.
        matching_indicators = self.sip.get('/api/indicators?status=In Progress&bulk=true')
        self.logger.info(f'There are {len(matching_indicators)} In Progress indicators.')
        for indicator in matching_indicators:
            print(indicator['id'])
            print(indicator['value'])
            print()

        print('Found {} indicators'.format(len(matching_indicators)))
        proceed = input('Proceed with enabling these indicators (y/n)? ')
        if proceed == 'y':
            for indicator in matching_indicators:
                self.enable_indicator(indicator)

    def get_indicator_type_report(self, sip_query_filter='status=Analyzed', print_report=True, write_report=True):
        ace = self.connect_to_ace()

        if not self.indicators:
            self.indicators = self.sip.get(f"/api/indicators?&{sip_query_filter}")

        total_analyzed_indicators = len(self.indicators)
        # The report results.
        # report = {'indicator_type': {'count': 53, 'dispo1': 17, 'dispo2': 484}}
        report = {'sip_query_filter': sip_query_filter,
                  'results': {}}

        # Set up the report structure and count the indicators by their type.
        for indicator in self.indicators:
            if indicator['type'] in report:
                report['results'][indicator['type']]['count'] += 1
            else:
                report['results'][indicator['type']] = {}
                report['results'][indicator['type']]['count'] = 1
                report['results'][indicator['type']]['total_alerts'] = 0
                report['results'][indicator['type']]['no_alerts'] = 0
                report['results'][indicator['type']]['manual_indicators'] = 0

        # Now check each indicator to see if it has alerted.
        desc = "Correlating SIP and ACE data"
        for indicator in tqdm(self.indicators, desc=desc):
            indicator_id = indicator['id']
            indicator_id_string = f"sip:{indicator['id']}"
            indicator_type = indicator['type']
            idata = self.sip.get(f"/api/indicators/{indicator_id}")
            if 'tags' in idata and 'manual_indicator' in idata['tags']:
                report['results'][indicator['type']]['manual_indicators'] += 1
    
            # Query the ACE database for this indicator ID.
            ace.execute("""SELECT * FROM
                                   observables o JOIN observable_mapping om ON o.id = om.observable_id
                                   JOIN alerts a ON a.id = om.alert_id
                               WHERE
                                   o.type = 'indicator' AND o.value = '""" + indicator_id_string + "' AND a.alert_type != 'faqueue'")
    
            # Get all of the results.
            results = ace.fetchall()
    
            # If we have alerted on this indicator...
            if results:
                # Collect the dispositions from every alert.
                dispositions = [alert['disposition'] for alert in results if alert['disposition']]

                # Store the unique dispositions in the report for the indicator type.
                for disposition in set(dispositions):
                    if disposition:
                        if disposition not in report['results'][indicator_type]:
                            report['results'][indicator_type][disposition] = 0

                # Store the disposition counts in the report structure.
                for disposition in dispositions:
                    if disposition:
                        report['results'][indicator_type][disposition] += 1

                report['results'][indicator_type]['total_alerts'] += len(dispositions)
            else:
                report['results'][indicator['type']]['no_alerts'] += 1

        self.logger.info(f"This report scanned {len(self.indicators)} indicators that matched: {sip_query_filter}")
       
        # write the report
        if write_report:
            report_name = f"indicator_report_{time.time()}.json"
            with open(report_name, 'w') as fp:
                json.dump(report, fp, indent=2)
            print(f"Wrote {report_name}")
        # print the report
        if print_report:
            self.print_indicator_report_summary(report)

    def print_indicator_report_summary(self, report):
        # Print the report. Start by getting a sorted list of the
        # different indicator types.
        indicator_types = sorted(report['results'].keys())
        for indicator_type in indicator_types:
            print(indicator_type)

            # Now get a sorted list of the alert dispositions.
            try:
                dispositions = sorted(report['results'][indicator_type].keys())
                for disposition in dispositions:
                    num = report['results'][indicator_type][disposition]
                    if report['results'][indicator_type]['total_alerts']:
                        percentage = (num / float(report['results'][indicator_type]['total_alerts'])) * 100
                    else:
                        percentage = 0
                    if disposition.isupper():
                        print('{}: {} = {:.2f}%'.format(disposition, report['results'][indicator_type][disposition], percentage))
                    else:
                        print('{}: {}'.format(disposition, report['results'][indicator_type][disposition]))
            except TypeError:
                print(report['results'][indicator_type]) 

            print()