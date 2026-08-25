## Config test
### pytest tests/test_config.py -v

======================================= test session starts ========================================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\User\MSC-software-eng\PersonalProject\DT\digital-twin\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\User\MSC-software-eng\PersonalProject\DT\digital-twin
configfile: pytest.ini
collected 12 items                                                                                  

tests/test_config.py::TestLoadBrokerConfig::test_password_auth_success PASSED                 [  8%]
tests/test_config.py::TestLoadBrokerConfig::test_cert_auth_success PASSED                     [ 16%]
tests/test_config.py::TestLoadBrokerConfig::test_missing_host_names_the_variable PASSED       [ 25%]
tests/test_config.py::TestLoadBrokerConfig::test_non_integer_port_raises_config_error_not_value_error PASSED [ 33%]
tests/test_config.py::TestLoadBrokerConfig::test_invalid_auth_mode_rejected PASSED            [ 41%]
tests/test_config.py::TestLoadBrokerConfig::test_cert_path_that_does_not_exist_is_rejected PASSED [ 50%]
tests/test_config.py::TestLoadInfluxConfig::test_success PASSED                               [ 58%]
tests/test_config.py::TestLoadInfluxConfig::test_missing_token_names_the_variable PASSED      [ 66%]
tests/test_config.py::TestLoadWorkloadConfig::test_success PASSED                             [ 75%]
tests/test_config.py::TestLoadWorkloadConfig::test_missing_asset_file_is_rejected PASSED      [ 83%]
tests/test_config.py::TestLoadWorkloadConfig::test_zero_interval_is_rejected PASSED           [ 91%]
tests/test_config.py::TestLoadWorkloadConfig::test_negative_interval_is_rejected PASSED       [100%]

======================================== 12 passed in 0.17s ========================================

## Loggind setup test
### pytest tests/test_logging_setup.py -v
(.venv) PS C:\Users\User\MSC-software-eng\PersonalProject\DT\digital-twin> pytest tests/test_logging_setup.py -v
==================================================== test session starts =====================================================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\User\MSC-software-eng\PersonalProject\DT\digital-twin\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\User\MSC-software-eng\PersonalProject\DT\digital-twin
configfile: pytest.ini
collected 9 items                                                                                                             

tests/test_logging_setup.py::TestSetupLogging::test_log_line_is_valid_json_with_required_fields PASSED                  [ 11%]
tests/test_logging_setup.py::TestSetupLogging::test_timestamp_is_iso8601_utc_with_millisecond_precision PASSED          [ 22%]
tests/test_logging_setup.py::TestSetupLogging::test_extra_fields_are_merged_into_payload PASSED                         [ 33%]
tests/test_logging_setup.py::TestSetupLogging::test_exception_info_is_captured PASSED                                   [ 44%]
tests/test_logging_setup.py::TestSetupLogging::test_repeated_setup_does_not_duplicate_handlers PASSED                   [ 55%]
tests/test_logging_setup.py::TestSetupLogging::test_explicit_level_overrides_default PASSED                             [ 66%]
tests/test_logging_setup.py::TestSetupLogging::test_log_level_env_var_used_when_no_explicit_level PASSED                [ 77%]
tests/test_logging_setup.py::TestSetupLogging::test_default_level_is_info_when_nothing_specified PASSED                 [ 88%]
tests/test_logging_setup.py::TestSetupLogging::test_does_not_propagate_to_root_logger PASSED                            [100%]

===================================================== 9 passed in 0.10s ======================================================


## Payload tests
### pytest tests/test_payload.py -v

==================================================== test session starts =====================================================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\User\MSC-software-eng\PersonalProject\DT\digital-twin\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\User\MSC-software-eng\PersonalProject\DT\digital-twin
configfile: pytest.ini
collected 20 items                                                                                                            

tests/test_payload.py::TestBuildPayload::test_builds_a_valid_payload PASSED                                             [  5%]
tests/test_payload.py::TestBuildPayload::test_rejects_empty_asset_id PASSED                                             [ 10%]
tests/test_payload.py::TestBuildPayload::test_rejects_negative_sequence PASSED                                          [ 15%]
tests/test_payload.py::TestBuildPayload::test_rejects_non_integer_sequence PASSED                                       [ 20%]
tests/test_payload.py::TestBuildPayload::test_rejects_bool_as_sequence PASSED                                           [ 25%]
tests/test_payload.py::TestBuildPayload::test_rejects_naive_timestamp PASSED                                            [ 30%]
tests/test_payload.py::TestBuildPayload::test_rejects_non_utc_timestamp PASSED                                          [ 35%]
tests/test_payload.py::TestBuildPayload::test_rejects_missing_channel PASSED                                            [ 40%]
tests/test_payload.py::TestBuildPayload::test_rejects_unexpected_channel PASSED                                         [ 45%]
tests/test_payload.py::TestBuildPayload::test_rejects_non_numeric_channel_value PASSED                                  [ 50%]
tests/test_payload.py::TestRoundTrip::test_parse_of_serialize_equals_original PASSED                                    [ 55%]
tests/test_payload.py::TestRoundTrip::test_round_trip_preserves_every_field_value PASSED                                [ 60%]
tests/test_payload.py::TestParseRejectsMalformedInput::test_rejects_non_json_bytes PASSED                               [ 65%]
tests/test_payload.py::TestParseRejectsMalformedInput::test_rejects_json_that_is_not_an_object PASSED                   [ 70%]
tests/test_payload.py::TestParseRejectsMalformedInput::test_rejects_missing_field PASSED                                [ 75%]
tests/test_payload.py::TestParseRejectsMalformedInput::test_rejects_unexpected_field PASSED                             [ 80%]
tests/test_payload.py::TestParseRejectsMalformedInput::test_rejects_wrong_schema_version PASSED                         [ 85%]
tests/test_payload.py::TestParseRejectsMalformedInput::test_rejects_negative_sequence PASSED                            [ 90%]
tests/test_payload.py::TestParseRejectsMalformedInput::test_rejects_non_numeric_channel PASSED                          [ 95%]
tests/test_payload.py::TestMeasuredByteSize::test_representative_payload_is_248_bytes PASSED                            [100%]

===================================================== 20 passed in 0.16s =====================================================



## Simulator test
### pytest tests/test_simulator.py -v
- failed test is fine its just the boundary time not running 

==================================================== test session starts ====================================================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\User\MSC-software-eng\PersonalProject\DT\digital-twin\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\User\MSC-software-eng\PersonalProject\DT\digital-twin
configfile: pytest.ini
collected 13 items                                                                                                           

tests/test_simulator.py::TestOutsideOperatingHours::test_returns_ambient_before_start PASSED                           [  7%]
tests/test_simulator.py::TestOutsideOperatingHours::test_returns_ambient_after_end PASSED                              [ 15%]
tests/test_simulator.py::TestBoilerOnOff::test_boiler_on_in_first_half_of_cycle PASSED                                 [ 23%]
tests/test_simulator.py::TestBoilerOnOff::test_boiler_off_in_second_half_of_cycle PASSED                               [ 30%]
tests/test_simulator.py::TestBoilerOnOff::test_boiler_cycles_predictably FAILED                                        [ 38%]
tests/test_simulator.py::TestNewtonsCooling::test_supply_temp_on_is_higher_than_baseline PASSED                        [ 46%]
tests/test_simulator.py::TestNewtonsCooling::test_supply_temp_off_approaches_ambient PASSED                            [ 53%]
tests/test_simulator.py::TestNewtonsCooling::test_return_temperature_delta_preserved PASSED                            [ 61%]
tests/test_simulator.py::TestNewtonsCooling::test_exponential_approach_heating PASSED                                  [ 69%]
tests/test_simulator.py::TestAmbientsAndSetpoint::test_setpoint_always_reported PASSED                                 [ 76%]
tests/test_simulator.py::TestAmbientsAndSetpoint::test_ambient_temperature_passed_through PASSED                       [ 84%]
tests/test_simulator.py::TestTimezoneValidation::test_rejects_naive_timestamp PASSED                                   [ 92%]
tests/test_simulator.py::TestTimezoneValidation::test_rejects_non_utc_timezone PASSED                                  [100%]

========================================================= FAILURES ==========================================================
______________________________________ TestBoilerOnOff.test_boiler_cycles_predictably _______________________________________

self = <test_simulator.TestBoilerOnOff object at 0x000001842C37B810>
boiler_config = {'steady_state': {'supply_temperature': 65.0, 'return_temperature': 55.0, 'ambient_baseline': 20.0}, 'dynamics': {'hea...duty_cycle': {'operating_hours_start': 6, 'operating_hours_end': 22, 'cycle_period_seconds': 1200, 'on_fraction': 0.5}}

    def test_boiler_cycles_predictably(self, boiler_config):
        # Multiple points through one 20-min cycle
        times_and_expected_power = [
            (_timestamp(6, 5), 5.0),   # 5 min: on
            (_timestamp(6, 10), 5.0),  # 10 min: on
            (_timestamp(6, 11), 0.0),  # 11 min: off
            (_timestamp(6, 20), 0.0),  # 20 min: off
            (_timestamp(6, 21), 5.0),  # 21 min: cycle repeats, on
        ]
    
        for ts, expected_power in times_and_expected_power:
            result = simulate(boiler_config, ts, 15.0)
>           assert result["power_draw_kw"] == expected_power
E           assert 0.0 == 5.0

tests\test_simulator.py:88: AssertionError
================================================== short test summary info ==================================================
FAILED tests/test_simulator.py::TestBoilerOnOff::test_boiler_cycles_predictably - assert 0.0 == 5.0
=============================================== 1 failed, 12 passed in 0.26s ===============================================