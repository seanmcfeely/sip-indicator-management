# sip-indicator-management

This tool manages SIP indicators based on tuning configurations for ACE ecosystems.

## Install

1. `git clone` this repo and `cd sip-indicator-management`
2. Create a virtual environment and install requirements with these three commands:
    ```console
    python3.9 -m venv venv
    source venv/bin/activate
    pip install -r requirements
    ```

Now, after you have your configuration complete you can try to manually execute it. When you're getting the desired results, you can set a cron job to routinely execute your tuning requirements. There is an example cron job included in this project.

## Tuning Configs

There is a config template at `indicator_management/etc/template.config.ini` that can be copied to `etc/config.ini` for first time setups. Supply the requirements for connecting to SIP and ACE.

Next, you need to create tuning configurations that describe the tunes you would like to make. Note that I am calling a "tune" the act of turning off indicators.

There are some examples in the `indicator_management/etc/template.config.ini` for creating tuning config sections. These tuning sections must have a name that starts with `tune_`.

## Execution

Manual executions can be achieved by using the CLI tool. The `bin/manage_indicator_intel` script can be used for scheduling executions via a cron job.

The CLI tool:

```console
$ ./IndicatorManagement.py -h
usage: IndicatorManagement.py [-h] [-d] [--logging-config LOGGING_CONFIG] [--dev] {reset_in_progress,tune_intel} ...

SIP indicator management for ACE ecosystems.

positional arguments:
  {reset_in_progress,tune_intel}
                        Various commands for the Indicator Manager
    reset_in_progress   Reset In Progress indicators to New.
    tune_intel          Find all Analyzed indicators matching tuning configurations and turn them off.

optional arguments:
  -h, --help            show this help message and exit
  -d, --debug           Turn on debug logging.
  --logging-config LOGGING_CONFIG
                        Path to logging configuration file. Defaults to etc/logging.ini
  --dev                 Interact with dev SIP instead of production.
```

Example cron job:

```
$ cat cron 
14 2 * * * /opt/intel/sip-indicator-management/bin/manage_indicator_intel 2> /opt/intel/sip-indicator-management/logs/cron.log
```

### Print Indicator Scope only

To see how many indicators are in scope for your tunes: `./IndicatorManagement.py tune_intel --print-scope-only`

### To See How many Indicators would get turned off

This will execute as normal by evaluating ACE's historical data for each indicator (takes awhile) but at the end will just display the result and exit without turning off the indicators.

`./IndicatorManagement.py tune_intel --dry-run`

## Logging

Logs are kept in the `logs` dir for seven days to review changes.

## Un-doing a Change

Fourteen days of changes are saved in the `var/records` directory. You can change how many days of records are retained by manually editing the find command inside of `bin/cleanup_records`.

The respective date of indicator changes are next level directories and the name of the tuning config that the changes applied under. For example, `var/records/2022-02-10/tune_external_intel` would exist if you had a tuning configuration section named `tune_external_intel` that turned off indicators on `2022-02-10`.

If a problem occurred and you need to turn indicators back on that got turned off, you can use this date to identify what indicators need to be turned back on. Additionally, there is a script at `bin/turn_indicators_on_for` for aiding with this purpose. The script requires the relative path to the directory containing the indicators you want to turn back on. Like: `bin/turn_indicators_on_for var/records/2022-02-10/tune_external_intel`.

Finally, you can un-do what you un-did (LOL) with an included `bin/turn_indicators_off_for` script. Example: `bin/turn_indicators_off_for var/records/2022-02-10/tune_external_intel`
