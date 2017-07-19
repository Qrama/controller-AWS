# Info
This is a subordinate charm for the Sojobo-api which enables the use of AWS-clouds

# Installation
The required charms can be found in the qrama-charms repo. In order to install these using the following commands, one must be in the topdir of the cloned qrama-charms repo.
```
juju deploy ./controller-google
juju add-relation sojobo-api controller-google
```
To disable AWS-clouds, just remove the application.
**Warning: Removing this will prevent the use of existing AWS-clouds!**

# Bugs
Report bugs on <a href="https://github.com/tengu-team/layer-controller-aws/issues">Github</a>

# Authors
- Mathijs Moerman <mathijs.moerman@tengu.io>
- Sébastien Pattyn <sebastien.pattyn@tengu.io>
