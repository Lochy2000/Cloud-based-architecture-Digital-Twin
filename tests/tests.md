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