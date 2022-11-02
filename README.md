# AWS Terminator

An AWS Lambda function for cleaning up AWS resources.

## Run the sanity tests

We use `tox` to run the sanity tests:

```console
$ tox
```

You can run one specific test with a `-e foo` parameter. Use `tox -av` to list them all:

```console
$ tox -e pylint
```
