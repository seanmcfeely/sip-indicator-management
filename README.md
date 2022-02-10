# sip-indicator-management

This tool manages SIP indicators based on tuning configurations for ACE ecosystems.

## Tuning Configs

There is a config template at `indicator_management/etc/template.config.ini` that can be copied to `etc/config.ini` for first time setups. Supply the requirements for connecting to SIP and ACE.

Next, you need to create tuning configurations that describe the tunes you would like to make. Note that I am calling a "tune" the act of turning off indicators.

There are some exampled in the `indicator_management/etc/template.config.ini` for creating tuning config sections. They must start with `tune_`.


## Un-doing a Change

Thirty days of changes are saved in the `var/records` directory. The respective date of indicator changes are next level directories and the name of the tuning config that the changes applied under like `var/records/2022-02-10/tune_external_intel` for example, if you had a tuning configuration section named `tune_external_intel` that turned off indicators on `2022-02-10`.

If a problem occurred and you need to turn indicators back on that got turned off, you can use this date to identify what indicators need to be turned back on. Additionally, there is a script at `bin/turn_indicators_back_on_for` for aiding with this purpose. The script requires the relative path to the directory containing the indicators you want to turn back on. Like: `bin/turn_indicators_back_on var/records/2022-02-10/tune_external_intel`

