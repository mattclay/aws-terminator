# Policy Categorization Guidelines

This document defines how IAM policy statements are organized across the
aws-terminator policy files. Follow these rules when adding, modifying, or
reviewing permissions.

---

## 1. Policy File Structure

Each policy file corresponds to a domain of AWS services:

| File | Services |
|------|----------|
| `compute.yaml` | EC2, Auto Scaling, ELB |
| `networking.yaml` | VPC, Route 53, API Gateway, Network Firewall |
| `data-services.yaml` | RDS, DynamoDB, ElastiCache, Redshift, DMS, Glacier, Glue, MSK |
| `storage-services.yaml` | S3, EFS, Backup, ECR, MemoryDB |
| `application-services.yaml` | CloudFormation, CloudWatch, CodeBuild, CodeCommit, CodePipeline, EventBridge, Kinesis, Lambda (logs), MQ, SES, SQS, SNS, SSM, Step Functions |
| `application-security.yaml` | WAF, WAFv2, Inspector |
| `security-services.yaml` | IAM, KMS, ACM, Secrets Manager, CloudTrail, STS, Access Analyzer |
| `paas.yaml` | Bedrock, CloudFront, ECS, EKS, Elastic Beanstalk, Lambda, Lightsail, SageMaker |

When adding a new service, place it in the file that best matches its domain.
When adding permissions for an existing service, add them to the file where that
service already lives.

---

## 2. Classification Dimensions

Every policy statement is classified along three dimensions:

### 2.1 Scope

| Value | Meaning | How It Works |
|-------|---------|--------------|
| **Global** | No explicit region condition | Used for statements without `aws:RequestedRegion` or `ec2:Region` conditions -- including resource-restricted statements where the region is embedded in the ARN |
| **Regional** | Restricted to a specific AWS region via an explicit condition | Used when a statement has `ec2:Region` or `aws:RequestedRegion` condition |

### 2.2 Resource Restriction

| Value | Meaning | `Resource` Field |
|-------|---------|------------------|
| **RestrictedResource** | Actions are scoped to specific ARN patterns | Specific ARN list (e.g., `arn:aws:sagemaker:{{ aws_region }}:{{ aws_account_id }}:image/*`) |
| **UnrestrictedResource** | Actions apply to all resources | `"*"` |

The word order `RestrictedResource` mirrors `UnrestrictedResource` -- the adjective
always comes before "Resource".

### 2.3 Cost

| Value | Meaning | Examples |
|-------|---------|----------|
| **WhichIncurFees** | At least one action in the statement can create or run billable resources | `ec2:RunInstances`, `rds:CreateDBInstance`, `lambda:InvokeFunction` |
| **WhichIncurNoFees** | No action in the statement creates billable resources | `ec2:Describe*`, `rds:ModifyDBInstance`, `s3:PutBucketTagging` |

When in doubt, check the AWS pricing page. If the API call itself can trigger
charges (not just the resource existing), classify as IncurFees.

---

## 3. Statement Naming Convention

Every statement Sid follows this pattern:

```
Allow{Scope}{Resource}Actions{Cost}
```

| Component | Values |
|-----------|--------|
| `{Scope}` | `Global` \| `Regional` (always present) |
| `{Resource}` | `UnrestrictedResource` \| `RestrictedResource` |
| `{Cost}` | `WhichIncurFees` \| `WhichIncurNoFees` |

Examples:

```
AllowGlobalUnrestrictedResourceActionsWhichIncurNoFees    Resource: "*"
AllowGlobalRestrictedResourceActionsWhichIncurFees        Resource: specific ARNs
AllowGlobalRestrictedResourceActionsWhichIncurNoFees      Resource: specific ARNs
AllowRegionalUnrestrictedResourceActionsWhichIncurNoFees  Resource: "*" + region condition
AllowRegionalRestrictedResourceActionsWhichIncurFees      Resource: specific ARNs
```

Special-purpose statements (service-linked roles, conditional attach/detach,
third-party access) may use descriptive Sids but should still start with `Allow`.
Examples: `AllowServiceLinkedRoleCreation`, `AllowKafkaActions`,
`AllowLambdaEventSourceMappings`, `PermitReadOnlyThirdParty`.

---

## 4. Action Placement Rules

### 4.1 Determine the Action Type

| Type | Patterns | Examples |
|------|----------|----------|
| **Read-only** | `Describe*`, `Get*`, `List*` | `rds:DescribeDBInstances`, `s3:GetObject` |
| **Write** | Everything else | `Create*`, `Delete*`, `Update*`, `Put*`, `Modify*`, `Tag*`, `Untag*`, `Add*`, `Remove*` |

### 4.2 Place Read-Only Actions

Read-only actions go in the **Unrestricted, NoFees** section.

Rationale: read-only operations do not mutate state and do not create resources.
In a test account context, restricting them to specific ARNs adds maintenance
burden without meaningful security benefit.

**Exceptions -- keep these resource-restricted even though they are read-only:**

| Action | Reason |
|--------|--------|
| `secretsmanager:GetSecretValue` | Exposes secret contents |
| `kms:Decrypt` | Decrypts arbitrary data (cryptographic operation, not a pure read) |
| `iam:GetCredentialReport` | Exposes credential metadata for all IAM users |
| `iam:GetAccountAuthorizationDetails` | Dumps all IAM policies, roles, users, groups |
| `iam:GetAccessKeyLastUsed` | Reveals access key usage patterns |
| `iam:GetLoginProfile` | Reveals whether console login exists |
| `ssm:GetParameter` / `GetParameters` / `GetParametersByPath` | Can expose secrets stored in SSM Parameter Store |

The test: "Could an unrestricted read of this type across the account expose
sensitive data?" If yes, keep it resource-restricted.

### 4.3 Place Write Actions

Determine whether the API takes a specific resource ARN (or resource identifier
that maps to an ARN) as input:

| Takes specific ARN? | Placement |
|---------------------|-----------|
| **Yes** | Resource-restricted, scoped to the relevant ARN patterns |
| **No** (creates a new resource or is a global operation) | Unrestricted (no choice) |

How to check: look at the AWS API reference for the action. If the request
requires a resource identifier (ARN, name, ID), the action can and should be
resource-restricted.

### 4.4 Tagging Actions

Tagging actions are **write operations** and always take a resource ARN. They
must always go in **resource-restricted** sections.

| Action Pattern | Takes ARN? | Placement |
|---------------|------------|-----------|
| `TagResource` / `UntagResource` | Yes | Resource-restricted |
| `AddTags` / `DeleteTags` / `RemoveTags` | Yes | Resource-restricted |
| `AddTagsToResource` / `RemoveTagsFromResource` | Yes | Resource-restricted |
| `ListTags` / `ListTagsForResource` / `ListTagsOfResource` | Yes (takes ARN) | **Unrestricted** -- it is a read-only action (follows Rule 4.2). Group it with `Describe*` and `List*`, not with the write tagging actions. |
| `CreateTags` / `DeleteTags` (EC2-style) | Yes | Resource-restricted |
| `PutBucketTagging` (S3-style) | Yes | Resource-restricted |

### 4.5 Decision Flowchart

```
                        Is it read-only? (Describe/Get/List)
                       /                                    \
                     Yes                                     No (Write action)
                      |                                       |
              Exposes sensitive data?                  Takes a specific resource ARN?
              (see exceptions table)                        |
              /                   \                   /                              \
            Yes                    No               Yes                               No
             |                      |                |                                 |
    Resource-restricted,     Unrestricted,     Resource-restricted              Unrestricted
    NoFees                   NoFees                  |                                 |
                                              Creates billable              Creates billable
                                              resources?                    resources?
                                             /            \                /            \
                                           Yes             No            Yes             No
                                            |               |            |               |
                                      Restricted,     Restricted,   Unrestricted,   Unrestricted,
                                      IncurFees       IncurNoFees   IncurFees       IncurNoFees
```

**Grouping footnote**: In practice, a sensitive read-only action (e.g.,
`secretsmanager:Get*`) may share a statement with related write actions for the
same service. When this happens, the action still gets the correct Resource
restriction -- only the cost label may be imprecise. Prefer correct resource
scoping over strict cost labeling.

---

## 5. Wildcarding Guidelines

### 5.1 General Rules

| Pattern | Safe to Wildcard? | Rationale |
|---------|-------------------|-----------|
| `service:Describe*` | **Yes** | All Describe actions are read-only |
| `service:Get*` | **Service-dependent** | Safe for most services. **UNSAFE for IAM, SSM, KMS, Secrets Manager** -- see Section 5.2 |
| `service:List*` | **Yes** | All List actions are read-only, including `ListTags` variants (which take an ARN but only read tags, not modify them) |
| `service:Create*` | **No** | Too broad; could grant create on unexpected resource types |
| `service:Delete*` | **No** | Could allow deleting unexpected resources |
| `service:Update*` | **No** | Same reasoning |
| `service:*Tags` | **Yes, if clean** | Verify no unintended matches by checking the full API list for the service |
| `service:Tag*` / `service:Untag*` | **Case by case** | `iam:Tag*` matches `TagRole`, `TagUser`, `TagPolicy`, etc. -- acceptable if all are desired |

Before using any wildcard, verify what it matches by checking the complete list
of actions for that service in the
[IAM Actions Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/reference.html).
A wildcard that matches 4 intended actions and 0 unintended ones is safe. A
wildcard that also matches an unintended action is not.

### 5.2 Services Where `Get*` is UNSAFE in Unrestricted Sections

For these services, always list individual safe Get actions explicitly. Never
use `service:Get*` in an unrestricted (`Resource: "*"`) section.

| Service | `Get*` Includes | Risk |
|---------|----------------|------|
| **`iam`** | `GetCredentialReport`, `GetAccountAuthorizationDetails`, `GetAccessKeyLastUsed`, `GetLoginProfile` (26 total Get actions) | Exposes account-wide IAM configuration and credential metadata |
| **`ssm`** | `GetParameter`, `GetParameters`, `GetParametersByPath` (27 total Get actions) | SSM parameters often store secrets (DB passwords, API keys) |
| **`secretsmanager`** | `GetSecretValue` (3 total Get actions) | Directly exposes secret contents |
| **`kms`** | `GetParametersForImport` (4 total Get actions) | Exports key import parameters. `GetPublicKey` is safe (public keys are inherently shareable). Borderline for a test account but would not be acceptable in production. |

Safe individual actions to use instead:

| Service | Safe to List Individually in Unrestricted |
|---------|------------------------------------------|
| `iam` | `iam:GetRole`, `iam:GetUser`, `iam:GetInstanceProfile`, `iam:GetSAMLProvider`, `iam:GetServerCertificate` |
| `ssm` | `ssm:GetDocument`, `ssm:GetCommandInvocation`, `ssm:GetConnectionStatus`, `ssm:GetInventory`, `ssm:GetInventorySchema`, `ssm:GetMaintenanceWindow*`, `ssm:GetServiceSetting` |
| `secretsmanager` | `secretsmanager:GetRandomPassword`, `secretsmanager:GetResourcePolicy` |
| `kms` | `kms:GetKeyPolicy`, `kms:GetKeyRotationStatus`, `kms:GetPublicKey` |

### 5.3 Services Where `Get*` IS Safe in Unrestricted Sections

| Service | Reason |
|---------|--------|
| `lambda` | All 17 Get actions are read-only metadata. `GetFunction` includes a pre-signed code download URL but this is acceptable in a test account. |
| `acm` | Only 2 Get actions: `GetAccountConfiguration`, `GetCertificate` (returns cert body but NOT the private key -- private keys never leave ACM). |
| `s3` | `GetObject` returns object data but in a test account this is acceptable. |
| `ec2` | All Get actions return instance/resource metadata. |
| `eks`, `lightsail`, `cloudfront`, `rds`, `dynamodb`, `ecr`, `glue` | All Get actions return metadata only. |
| `waf`, `wafv2`, `cloudformation`, `codecommit`, `codepipeline`, `ses`, `sqs`, `SNS` | All Get actions return configuration/metadata. |

---

## 6. Region Scoping

There are three valid mechanisms for regional restriction. Use exactly one per
statement -- do not mix them.

| Mechanism | When to Use | Example |
|-----------|-------------|---------|
| Region in ARN | Resource-restricted statements | `arn:aws:sagemaker:{{ aws_region }}:{{ aws_account_id }}:image/*` |
| `aws:RequestedRegion` condition | Unrestricted statements for non-EC2 services | `Condition: { StringEquals: { aws:RequestedRegion: '{{ aws_region }}' } }` |
| `ec2:Region` condition | Unrestricted statements for EC2-specific actions | `Condition: { StringEquals: { ec2:Region: '{{ aws_region }}' } }` |

**Do not add a redundant region condition** to a resource-restricted statement
whose ARN patterns already contain `{{ aws_region }}`.

---

## 7. Adding a New Service

When adding permissions for a new AWS service, follow this checklist:

### Step 1: Choose the policy file

Place the service in the file matching its domain (see Section 1).

### Step 2: Classify each action

For every action the tests need, apply the decision flowchart (Section 4.5):

1. Is it read-only (`Describe*`, `Get*`, `List*`)?
   - If yes and not sensitive: add to the **Unrestricted, NoFees** section
   - If yes and sensitive: add to a **Resource-restricted, NoFees** section
2. Is it a write action that takes a resource ARN?
   - Add to the **Resource-restricted** section
   - Classify as IncurFees or IncurNoFees based on whether it creates billable resources
3. Is it a write action that does NOT take a resource ARN (e.g., `CreateXxx`)?
   - Add to the **Unrestricted** section
   - Classify as IncurFees or IncurNoFees

### Step 3: Add resource ARN patterns

For every resource type used by your service's resource-restricted actions, add
the ARN pattern to the Resource block:

```yaml
- 'arn:aws:{service}:{{ aws_region }}:{{ aws_account_id }}:{resource-type}/*'
```

### Step 4: Check tagging actions

If the service uses tagging (`AddTags`, `DeleteTags`, `ListTags`, `TagResource`,
etc.), these are write actions that take ARNs. Always place them in the
**resource-restricted** section, even if they feel like "just metadata."

### Step 5: Verify wildcard safety

If you want to use `Describe*` or `Get*` wildcards:

1. Look up the full list of actions for the service in the IAM documentation
2. Verify no sensitive actions match the wildcard
3. If unsafe matches exist, list individual safe actions explicitly

### Step 6: Add a terminator class (if applicable)

If the service creates resources that need cleanup, add a Terminator subclass in
the corresponding `aws/terminator/*.py` file. See existing classes for patterns.

Consider adding:
- An `ignore` property to skip resources in transient states (`CREATING`,
  `DELETING`, etc.) to avoid noisy error logs
- Dependency cleanup in `terminate()` if the resource has child resources that
  must be deleted first

---

## 8. Quick Reference: Common Patterns

### Read-only actions (unrestricted)
```yaml
- Sid: AllowGlobalUnrestrictedResourceActionsWhichIncurNoFees
  Effect: Allow
  Action:
    - newservice:Describe*
    - newservice:Get*
    - newservice:List*
  Resource: "*"
```

### Write actions (resource-restricted, no fees)
```yaml
- Sid: AllowGlobalRestrictedResourceActionsWhichIncurNoFees
  Effect: Allow
  Action:
    - newservice:AddTags
    - newservice:CreateThing
    - newservice:DeleteTags
    - newservice:DeleteThing
    - newservice:UpdateThing
  Resource:
    - 'arn:aws:newservice:{{ aws_region }}:{{ aws_account_id }}:thing/*'
```

### Write actions (resource-restricted, with fees)
```yaml
- Sid: AllowGlobalRestrictedResourceActionsWhichIncurFees
  Effect: Allow
  Action:
    - newservice:RunThing
  Resource:
    - 'arn:aws:newservice:{{ aws_region }}:{{ aws_account_id }}:thing/*'
```

### Enumeration-only writes (unrestricted, no choice)
```yaml
# Only when the API genuinely doesn't take a resource ARN
- Sid: AllowGlobalUnrestrictedResourceActionsWhichIncurNoFees
  Effect: Allow
  Action:
    - newservice:CreateThing   # Creates new, no ARN input
  Resource: "*"
```
