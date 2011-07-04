Feature: Be able to remove packages

Scenario: Install then Uninstall gevent
    Given I use "standard" environment
    When I execute pyg install gevent
    Then the return code is 0
    When I execute pyg check gevent
    Then a single line matches True
    Then the return code is 0
    When I execute pyg remove -y gevent
    Then the return code is 0
    When I execute pyg check gevent
    Then one line matches False
    Then the return code is 0