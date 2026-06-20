[discovery-request] Add versioning_status to S3 discovery

The scanning team requires versioning information to identify buckets
where versioning is disabled. This is needed to flag buckets that lack
protection against accidental deletion.

Please add versioning_status to the S3 discovery YAML.

Requested by: scanning-team
Priority: medium
