# AWS Terminator Policy Categorization Framework

## Document Purpose

This document defines the rules for how IAM policy statements should be categorized
across the aws-terminator policy files. It audits the current state, identifies
inconsistencies, and provides a detailed implementation plan to bring all policy files
into alignment.

---

## 1. Categorization Framework

### 1.1 Classification Dimensions

Every IAM policy statement is classified along three dimensions:

| Dimension | Values | Description |
|-----------|--------|-------------|
| **Scope** | `Global`, `Regional`, or omitted | Whether the statement is constrained to a specific AWS region via an IAM condition. Omitted when region scoping is achieved through the resource ARN pattern instead. |
| **Resource** | `ResourceRestricted` or `UnrestrictedResource` | Whether the `Resource` field lists specific ARN patterns (`ResourceRestricted`) or uses `"*"` (`UnrestrictedResource`). |
| **Cost** | `WhichIncurFees` or `WhichIncurNoFees` | Whether any action in the statement can create or run billable AWS resources. |

### 1.2 Sid Naming Convention

Every statement Sid should follow this pattern:

```
Allow{Scope}{Resource}Actions{Cost}
```

Where:
- `{Scope}` = `Global` | `Regional` | (empty)
- `{Resource}` = `UnrestrictedResource` | `ResourceRestricted`
- `{Cost}` = `WhichIncurFees` | `WhichIncurNoFees`

Examples:
- `AllowGlobalUnrestrictedResourceActionsWhichIncurNoFees`
- `AllowRegionalResourceRestrictedActionsWhichIncurFees`
- `AllowResourceRestrictedActionsWhichIncurNoFees`

Special-purpose statements (service-linked roles, conditional attach/detach, third-party
access) may use descriptive Sids outside this convention, but should still include the
`Allow` prefix.

### 1.3 Region Scoping Mechanisms

There are three valid ways to scope a statement to a region:

| Mechanism | When to Use |
|-----------|-------------|
| Region embedded in resource ARN (e.g., `arn:aws:sagemaker:{{ aws_region }}:...`) | Resource-restricted statements. The ARN itself limits the region. No condition needed. |
| `aws:RequestedRegion` condition | Unrestricted (`Resource: "*"`) statements for non-EC2 services. This is the standard cross-service condition key. |
| `ec2:Region` condition | Unrestricted statements for EC2-specific actions only. EC2 uses its own condition key. |

Do NOT mix mechanisms within the same statement. Regional resource-restricted
statements should not add a redundant region condition if the ARN already contains the
region.

---

## 2. Action Placement Rules

For every action being added to a policy, apply these rules in order to determine the
correct statement placement.

### Rule 1: Determine the action type

| Type | Pattern | Examples |
|------|---------|----------|
| **Read-only** | `Describe*`, `Get*`, `List*` | `rds:DescribeDBInstances`, `s3:GetObject`, `ec2:DescribeInstances` |
| **Write** | Everything else | `Create*`, `Delete*`, `Update*`, `Put*`, `Modify*`, `Tag*`, `Untag*`, `Add*`, `Remove*` |

**Exception**: `ListTags` (in services like SageMaker) takes a required `ResourceArn`
parameter despite its `List` prefix. Classify it as a resource-targeted read, not a
general enumeration. See Rule 3.

### Rule 2: Place read-only actions

Read-only actions go in the **Unrestricted, NoFees** section.

Rationale: read-only operations do not mutate state, do not create resources, and in
the context of a test account do not expose sensitive information. Restricting them to
specific ARNs adds maintenance burden without meaningful security benefit.

**Exceptions -- keep these resource-restricted even though they are read-only:**

| Action | Reason |
|--------|--------|
| `secretsmanager:GetSecretValue` | Exposes secret contents |
| `kms:Decrypt` | Decrypts arbitrary data using any key. **Note**: Decrypt is a cryptographic operation, not a pure read -- AWS classifies it as a write action. Listed here because it appears alongside read-only Get actions and must stay resource-restricted for the same reason. |
| `kms:GetPublicKey` | Exports key material |
| `iam:GetCredentialReport` | Exposes credential metadata for all IAM users |
| `iam:GetAccountAuthorizationDetails` | Dumps all IAM policies, roles, users, groups |
| `iam:GetAccessKeyLastUsed` | Reveals access key usage patterns |
| `iam:GetLoginProfile` | Reveals whether console login exists |
| `ssm:GetParameter` / `GetParameters` / `GetParametersByPath` | Can expose secrets stored in SSM Parameter Store |

The test is: "Could an unrestricted read of this type across the account cause harm
or expose sensitive data?" If no, unrestricted. If yes, restrict.

**Important**: Because of these exceptions, `iam:Get*` and `ssm:Get*` must NEVER be
wildcarded in an unrestricted section. Always list the specific safe Get actions
individually (e.g., `iam:GetRole`, `iam:GetUser`).

### Rule 3: Place write actions by ARN behavior

Determine whether the action's API takes a specific resource ARN as input:

| API takes specific ARN? | Placement |
|------------------------|-----------|
| **Yes** | Resource-restricted section, scoped to the relevant ARN patterns |
| **No** (global/enumeration operation) | Unrestricted section (no choice) |

How to check: look at the AWS API reference for the action. If the request requires a
resource identifier (ARN, name, ID) that maps to an IAM resource ARN, the action can
and should be resource-restricted.

**Tagging actions deserve special attention:**

| Action Pattern | Takes ARN? | Correct Placement |
|---------------|------------|-------------------|
| `TagResource` / `UntagResource` | Yes (always) | Resource-restricted |
| `AddTags` / `DeleteTags` / `AddTagsToResource` / `RemoveTagsFromResource` | Yes (always) | Resource-restricted |
| `ListTags` / `ListTagsForResource` | Yes (takes ARN) | **Unrestricted** -- read-only action, follows Rule 2. Group with `Describe*` and `List*`, not with write tagging actions. |
| `CreateTags` / `DeleteTags` (EC2-style) | Yes (resource ID) | Resource-restricted (but EC2 uses region condition instead of ARN) |
| `PutBucketTagging` (S3-style) | Yes (bucket name) | Resource-restricted |

### Rule 4: Classify cost

| Creates or runs billable resources? | Classification |
|-------------------------------------|----------------|
| **Yes**: launches instances, creates clusters, invokes functions, allocates storage, starts tasks | `WhichIncurFees` |
| **No**: metadata operations, configuration, tagging, deletion, description | `WhichIncurNoFees` |

When in doubt, check the AWS pricing page for the service. If the API call alone can
trigger charges (not just the resource existing), it incurs fees.

### Rule 5: Wildcarding guidelines

| Pattern | Safe to Wildcard? | Rationale |
|---------|-------------------|-----------|
| `service:Describe*` | Yes | All Describe actions are read-only |
| `service:Get*` | Service-dependent | **DANGEROUS for IAM and SSM** -- see below. Safe for most other services. Always check the full list of Get actions for sensitive reads like `GetSecretValue`, `GetCredentialReport`, `GetParameter`. |
| `service:List*` | Usually yes | But `ListTags` takes an ARN -- if it's in restricted section, don't wildcard List* there |
| `service:Create*` | No | Too broad for mutating actions; could grant create on unexpected resource types |
| `service:Delete*` | No | Same as above; could allow deleting unexpected resources |
| `service:Update*` | No | Same reasoning |
| `service:*Tags` | Yes, if clean | Verify no unintended matches (check AWS API list for the service) |
| `service:Tag*` / `service:Untag*` | Case by case | `iam:Tag*` matches `TagRole`, `TagUser`, etc. -- acceptable if all are desired |

Before using a wildcard, verify what it matches by checking the full list of actions for
that service in the IAM documentation. A wildcard that matches 4 intended actions and 0
unintended ones is safe. A wildcard that also matches an unintended action is not.

**Services where `Get*` wildcarding is UNSAFE in unrestricted sections:**

| Service | `Get*` includes | Risk |
|---------|----------------|------|
| `iam` | `GetCredentialReport`, `GetAccountAuthorizationDetails`, `GetAccessKeyLastUsed`, `GetLoginProfile` (26 total Get actions) | Exposes account-wide IAM configuration and credential metadata |
| `ssm` | `GetParameter`, `GetParameters`, `GetParametersByPath` (27 total Get actions) | SSM parameters often store secrets (DB passwords, API keys) |
| `secretsmanager` | `GetSecretValue` (3 total Get actions) | Directly exposes secret contents |
| `kms` | `GetPublicKey`, `GetParametersForImport` (4 total Get actions) | Exports key material. **Borderline**: `GetPublicKey` returns the public half (not secret), `GetParametersForImport` returns ephemeral import tokens. Already wildcarded unrestricted in current policy -- acceptable for a test account but would not be in production. |

For these services, always list individual safe Get actions explicitly:
- `iam`: use `iam:GetRole`, `iam:GetUser`, `iam:GetInstanceProfile`, etc.
- `ssm`: use `ssm:GetDocument`, `ssm:GetCommandInvocation`, etc.
- `secretsmanager`: use `secretsmanager:GetRandomPassword`, `secretsmanager:GetResourcePolicy`
- `kms`: use `kms:GetKeyPolicy`, `kms:GetKeyRotationStatus`

**Services where `Get*` wildcarding is SAFE in unrestricted sections:**

| Service | Reason |
|---------|--------|
| `lambda` | All 17 Get actions are read-only metadata (function config, aliases, policies). `GetFunction` returns a code download URL but this is acceptable in a test account. |
| `acm` | Only 2 Get actions: `GetAccountConfiguration`, `GetCertificate` (returns cert body but NOT private key). |
| `s3` | Already unrestricted in the current policy. `GetObject` returns object data but in a test account this is acceptable. |
| `eks`, `lightsail`, `cloudfront`, `rds`, `dynamodb` | All Get actions return metadata only. |

### Decision Flowchart

```
                        Is it read-only? (Describe/Get/List)
                       /                                    \
                     Yes                                     No (Write action)
                      |                                       |
              Exposes sensitive data?                  Takes a specific resource ARN?
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

**Flowchart footnote**: In practice, a sensitive read-only action (e.g.,
`secretsmanager:Get*`) may share a statement with write actions in a "IncurFees"
section for grouping convenience. The flowchart shows the ideal classification;
actual placement may differ when co-locating with related write actions avoids
creating a statement with only one or two actions. When this happens, the
action still gets the correct Resource restriction -- only the cost label is
imprecise.

---

## 3. Current State Audit

### 3.1 Read-Only Actions Incorrectly Resource-Restricted

These read-only actions are currently in resource-restricted sections but should be in
unrestricted sections per Rule 2.

#### paas.yaml

| Action | Current Sid | Impact |
|--------|-------------|--------|
| `eks:Describe*` | `AllowResourceRestrictedActionsWhichIncurNoFees` | Move to unrestricted |
| `eks:List*` | `AllowResourceRestrictedActionsWhichIncurNoFees` | Move to unrestricted |
| `elasticbeanstalk:Describe*` | `AllowResourceRestrictedActionsWhichIncurNoFees` | Move to unrestricted |
| `lightsail:Get*` | `AllowResourceRestrictedActionsWhichIncurNoFees` | Move to unrestricted |
| `lambda:GetAlias` | `AllowResourceRestrictedActionsWhichIncurNoFees` | Move to unrestricted |
| `lambda:GetFunction` | `AllowResourceRestrictedActionsWhichIncurNoFees` | Move to unrestricted |
| `lambda:GetFunctionConfiguration` | `AllowResourceRestrictedActionsWhichIncurNoFees` | Move to unrestricted |
| `lambda:GetLayerVersion` | `AllowResourceRestrictedActionsWhichIncurNoFees` | Move to unrestricted |
| `lambda:GetPolicy` | `AllowResourceRestrictedActionsWhichIncurNoFees` | Move to unrestricted |
| `lambda:ListLayerVersions` | `AllowResourceRestrictedActionsWhichIncurNoFees` | Move to unrestricted |
| `lambda:ListTags` | `AllowResourceRestrictedActionsWhichIncurNoFees` | Move to unrestricted (read-only, covered by `lambda:List*`) |

Note: After moving lambda Get/List actions, the unrestricted section can consolidate to
`lambda:Get*` and `lambda:List*` (since `lambda:GetEventSourceMapping` and
`lambda:List*` are already there).

#### application-services.yaml

| Action | Current Sid | Impact |
|--------|-------------|--------|
| `logs:Describe*` | `AllowGlobalResourceRestrictedActionsWhichIncurNoFees` | Move to unrestricted |

Note: `logs:List*` is already in the unrestricted section. After moving `logs:Describe*`,
all logs read-only actions would be unrestricted.

**EXISTING RISK: `ssm:Get*` is already wildcarded in the unrestricted section.** SSM has
27 Get actions including `ssm:GetParameter`, `ssm:GetParameters`, and
`ssm:GetParametersByPath` which can expose secrets stored in SSM Parameter Store. This
should be split: keep safe reads (`ssm:GetDocument`, `ssm:GetCommandInvocation`,
`ssm:GetConnectionStatus`, `ssm:GetInventory`, `ssm:GetInventorySchema`) in unrestricted,
and move `ssm:GetParameter*` to resource-restricted with
`arn:aws:ssm:{{ aws_region }}:{{ aws_account_id }}:parameter/*`. This is a pre-existing
issue, not introduced by any pending PR.

#### security-services.yaml

| Action | Current Sid | Impact |
|--------|-------------|--------|
| `acm:Describe*` | `ResourceRestrictedActionsWhichIncurNoFees` | Move to unrestricted |
| `acm:Get*` | `ResourceRestrictedActionsWhichIncurNoFees` | Move to unrestricted |
| `iam:GetSAMLProvider` | `ResourceRestrictedActionsWhichIncurNoFees` | Move to unrestricted |
| `iam:GetServerCertificate` | `ResourceRestrictedActionsWhichIncurNoFees` | Move to unrestricted |

Note: `iam:GetRole` and `iam:List*` are already in the unrestricted section.
`acm:List*` is already unrestricted. **Important**: `iam:GetInstanceProfile` is currently
caught by the `iam:*InstanceProfile` wildcard in the resource-restricted section (which
also covers `CreateInstanceProfile` and `DeleteInstanceProfile`). Do NOT move
`GetInstanceProfile` to unrestricted -- it must stay with its Create/Delete counterparts
under the `iam:*InstanceProfile` wildcard. Not all IAM read actions will be unrestricted
after this change.

### 3.2 Write/Tagging Actions Incorrectly Unrestricted

These write or tagging actions are currently in unrestricted (`Resource: "*"`) sections
but take a specific resource ARN and should be resource-restricted per Rule 3.

#### storage-services.yaml

| Action | Current Sid | Takes ARN? |
|--------|-------------|------------|
| `s3:CreateBucket` | `AllowGlobalUnrestrictedResourceActionsWhichIncurNoFees` | Yes (bucket name) |
| `s3:DeleteBucket` | Same | Yes |
| `s3:DeleteObject` | Same | Yes |
| `s3:DeleteObjects` | Same | Yes |
| `s3:PutObject` | Same | Yes |
| `s3:PutBucketTagging` | Same | Yes |
| `s3:DeleteBucketCors` | Same | Yes |
| `s3:DeleteBucketLifecycle` | Same | Yes |
| `s3:PutBucketAcl` | Same | Yes |
| `s3:PutBucketCors` | Same | Yes |
| `s3:PutBucketPolicy` | Same | Yes |
| `s3:PutBucketVersioning` | Same | Yes |
| `s3:PutEncryptionConfiguration` | Same | Yes |
| `s3:PutLifecycleConfiguration` | Same | Yes |
| `s3:PutReplicationConfiguration` | Same | Yes |
| `s3:PutBucketLogging` | Same | Yes |
| `s3:PutBucketNotification` | Same | Yes |
| `s3:PutBucketWebsite` | Same | Yes |
| `s3:DeleteBucketWebsite` | Same | Yes |
| `s3:PutBucketPublicAccessBlock` | Same | Yes |
| `s3:PutBucketOwnershipControls` | Same | Yes |
| `s3:DeleteBucketOwnershipControls` | Same | Yes |
| `s3:PutBucketObjectLockConfiguration` | Same | Yes |
| `s3:PutBucketRequestPayment` | Same | Yes |
| `s3:PutAccelerateConfiguration` | Same | Yes |
| `s3:CreateAccessPoint*` | Same | Yes |
| `s3:DeleteAccessPoint*` | Same | Yes |
| `s3:DeleteObjectTagging` | Same | Yes |
| `s3:DeleteObjectVersion` | Same | Yes |
| `s3:DeleteObjectVersionTagging` | Same | Yes |
| `s3:PutObjectAcl` | Same | Yes |
| `s3:PutObjectTagging` | Same | Yes |
| `s3:PutObjectVersionTagging` | Same | Yes |
| `s3:PutInventoryConfiguration` | Same | Yes |
| `s3:DeleteBucketMetricsConfiguration` | Same | Yes |
| `elasticfilesystem:CreateFileSystem` | Same | No (returns ARN, but doesn't take one) |
| `elasticfilesystem:CreateMountTarget` | Same | Yes (file system ID) |
| `elasticfilesystem:CreateTags` | Same | Yes |
| `elasticfilesystem:DeleteFileSystem` | Same | Yes |
| `elasticfilesystem:DeleteMountTarget` | Same | Yes |
| `elasticfilesystem:TagResource` | Same | Yes |
| `elasticfilesystem:UntagResource` | Same | Yes |
| `elasticfilesystem:UpdateFileSystem` | Same | Yes |
| `elasticfilesystem:PutLifecycleConfiguration` | Same | Yes |
| `backup:CreateBackupPlan` | Same | No (creates new) |
| `backup:CreateBackupSelection` | Same | Yes (plan ID) |
| `backup:CreateBackupVault` | Same | No (creates new) |
| `backup:DeleteBackupPlan` | Same | Yes |
| `backup:DeleteBackupSelection` | Same | Yes |
| `backup:DeleteBackupVault` | Same | Yes |
| `backup:TagResource` | Same | Yes |
| `backup:UntagResource` | Same | Yes |
| `backup:UpdateBackupPlan` | Same | Yes |
| `ecr:CreateRepository` | Same | No (creates new) |
| `ecr:PutImageTagMutability` | Same | Yes |

**Note on S3**: S3 is a special case. S3 bucket names are globally unique and not
predictable in the same way as other resources. The current approach of using
`Resource: "*"` for S3 is common in test accounts because S3 ARN patterns like
`arn:aws:s3:::ansible-test-*` would require all test buckets to follow a naming
convention. This is a pragmatic tradeoff. If a naming convention exists or can be
enforced, S3 actions should be resource-restricted.

**Note on EFS/backup**: Several `Create` actions (like `CreateFileSystem`,
`CreateBackupPlan`, `CreateBackupVault`, `ecr:CreateRepository`) don't take an ARN
because they create a new resource. These genuinely need `Resource: "*"`. However,
all other operations on those resources (Delete, Update, Tag) do take ARNs and
should be resource-restricted.

#### application-services.yaml

| Action | Current Sid | Takes ARN? |
|--------|-------------|------------|
| `sqs:CreateQueue` | `AllowGlobalUnrestrictedResourceActionsWhichIncurNoFees` | No (creates new) |
| `sqs:DeleteQueue` | Same | Yes (queue URL) |
| `sqs:SetQueueAttributes` | Same | Yes |
| `sqs:TagQueue` | Same | Yes |
| `sqs:UntagQueue` | Same | Yes |
| `ses:DeleteIdentity` | Same | Yes |
| `ses:DeleteIdentityPolicy` | Same | Yes |
| `ses:CreateReceiptRuleSet` | Same | No (creates new) |
| `ses:DeleteReceiptRuleSet` | Same | Yes |
| `ses:SetActiveReceiptRuleSet` | Same | Yes |
| `ses:PutIdentityPolicy` | Same | Yes |
| `ses:SetIdentityDkimEnabled` | Same | Yes |
| `ses:SetIdentityFeedbackForwardingEnabled` | Same | Yes |
| `ses:SetIdentityHeadersInNotificationsEnabled` | Same | Yes |
| `ses:SetIdentityNotificationTopic` | Same | Yes |
| `ses:VerifyDomainDkim` | Same | Yes |
| `ses:VerifyDomainIdentity` | Same | Yes |
| `ses:VerifyEmailIdentity` | Same | Yes |
| `ssm:AddTagsToResource` | Same | Yes |
| `ssm:RemoveTagsFromResource` | Same | Yes |
| `events:CreateRule` | Same | **Note: not a real IAM action** -- the correct action is `events:PutRule`. This is dead weight in the policy. |
| `events:DeleteRule` | Same | Yes |
| `events:PutRule` | Same | Yes (takes rule name, IAM evaluates against rule ARN) |
| `events:PutTargets` | Same | Yes |
| `events:RemoveTargets` | Same | Yes |

**Note on SES**: SES identity ARNs follow the pattern
`arn:aws:ses:region:account:identity/*`. Most SES actions can be resource-restricted.
However, SES is being superseded by SESv2 and the test coverage may be legacy.
Evaluate whether the effort of restructuring SES is worthwhile.

**Note on SQS**: SQS queue ARNs follow `arn:aws:sqs:region:account:*`. Delete,
SetAttributes, and tagging actions can be restricted. `CreateQueue` cannot (creates new).

#### security-services.yaml

| Action | Current Sid | Takes ARN? |
|--------|-------------|------------|
| `iam:Tag*` | `GlobalUnrestrictedResourceActionsWhichIncurNoFees` | Yes (role/user/etc ARN) |
| `iam:Untag*` | Same | Yes |
| `kms:CreateAlias` | Same | Yes (key ARN) |
| `kms:DeleteAlias` | Same | Yes |
| `kms:CreateGrant` | Same | Yes |
| `kms:RetireGrant` | Same | Yes |
| `kms:TagResource` | Same | Yes |
| `kms:UntagResource` | Same | Yes |
| `kms:PutKeyPolicy` | Same | Yes |
| `kms:UpdateGrant` | Same | Yes |
| `kms:UpdateKeyDescription` | Same | Yes |
| `kms:Sign` | Same | Yes |
| `kms:Verify` | Same | Yes |
| `kms:ScheduleKeyDeletion` | Same | Yes |
| `kms:Disable*` | Same | Yes |
| `kms:EnableKey*` | Same | Yes |

**Note on KMS**: Nearly all KMS write actions take a key ARN or alias ARN. The
resource-restricted section already has `kms:Decrypt` restricted to
`arn:aws:kms:{{ aws_region }}:{{ aws_account_id }}:key/ansible-test-*`. The same ARN
pattern should be used for the other KMS write actions. However, this requires that
all test KMS keys follow the `ansible-test-*` naming convention.

**Note on IAM**: `iam:Tag*` and `iam:Untag*` operate on roles, users, etc. The
resource-restricted section already has IAM role ARNs
(`arn:aws:iam::{{ aws_account_id }}:role/ansible-test-*`). These tagging actions
should be restricted to the same patterns.

#### application-security.yaml

| Action | Current Sid | Takes ARN? |
|--------|-------------|------------|
| `waf:TagResource` | `AllowRegionalUnrestrictedResourceActionsWhichIncurNoFees` | Yes |
| `waf:UntagResource` | Same | Yes |
| `wafv2:TagResource` | Same | Yes |
| `wafv2:UntagResource` | Same | Yes |

Note: All `waf:Create*`, `waf:Delete*`, `waf:Update*` actions are also in this
unrestricted section. WAF classic (v1) actions use `Resource: "*"` because WAF classic
does not support resource-level permissions in IAM. WAFv2 does support resource-level
permissions and its write actions should be evaluated for restriction (the fees section
already restricts wafv2).

#### data-services.yaml

| Action | Current Sid | Takes ARN? |
|--------|-------------|------------|
| `kafka:CreateCluster` | `KafkaCluster` (Resource: "*") | No (creates new) |
| `kafka:DeleteCluster` | Same | Yes |
| `kafka:CreateConfiguration` | Same | No (creates new) |
| `kafka:DeleteConfiguration` | Same | Yes |
| `kafka:RebootBroker` | Same | Yes |
| `kafka:TagResource` | Same | Yes |
| `kafka:UntagResource` | Same | Yes |
| `kafka:Update*` | Same | Yes |

The entire Kafka section uses `Resource: "*"`. Kafka ARNs follow
`arn:aws:kafka:region:account:cluster/*/*`, `arn:aws:kafka:region:account:configuration/*/*`.
Write actions should be resource-restricted.

### 3.3 Cost Misclassification

| File | Action | Current | Correct | Rationale |
|------|--------|---------|---------|-----------|
| `data-services.yaml` | `rds:CreateDBInstance` | NoFees | **IncurFees** | Creates a billable RDS instance |
| `data-services.yaml` | `rds:CreateDBInstanceReadReplica` | NoFees | **IncurFees** | Creates a billable replica |
| `data-services.yaml` | `rds:RestoreDBInstanceFromDBSnapshot` | NoFees | **IncurFees** | Creates a billable instance |
| `data-services.yaml` | `rds:RestoreDBInstanceFromS3` | NoFees | **IncurFees** | Creates a billable instance |
| `data-services.yaml` | `rds:RestoreDBInstanceToPointInTime` | NoFees | **IncurFees** | Creates a billable instance |
| `data-services.yaml` | `rds:RestoreDBClusterFromS3` | NoFees | **IncurFees** | Creates a billable cluster |
| `data-services.yaml` | `rds:RestoreDBClusterFromSnapshot` | NoFees | **IncurFees** | Creates a billable cluster |
| `data-services.yaml` | `rds:RestoreDBClusterToPointInTime` | NoFees | **IncurFees** | Creates a billable cluster |
| `data-services.yaml` | `rds:StartDBInstance` | NoFees | **IncurFees** | Starts billing |
| `data-services.yaml` | `rds:StartDBCluster` | NoFees | **IncurFees** | Starts billing |

Note: Moving these to a Fees section would require creating a new
`AllowGlobalRestrictedResourceActionsWhichIncurFees` statement with the RDS ARN patterns,
or adding them to the existing one. This is a correctness improvement but does not
change the actual IAM permissions granted -- it only affects how the policy is organized
for human readability.

### 3.4 Sid Naming Inconsistencies

| File | Current Sid | Standard Form |
|------|-------------|---------------|
| `compute.yaml` | `AllowGlobalResourceRestrictedActionsWhichIncurNoFees` | `AllowGlobalResourceRestrictedActionsWhichIncurNoFees` (OK, minor word order) |
| `security-services.yaml` | `RegionalUnrestrictedResourceActionsWhichIncurNoFees` | `AllowRegionalUnrestrictedResourceActionsWhichIncurNoFees` |
| `security-services.yaml` | `RegionalUnrestrictedResourceActionsWhichIncurFees` | `AllowRegionalUnrestrictedResourceActionsWhichIncurFees` |
| `security-services.yaml` | `GlobalUnrestrictedResourceActionsWhichIncurNoFees` | `AllowGlobalUnrestrictedResourceActionsWhichIncurNoFees` |
| `security-services.yaml` | `GlobalRestrictedResourceActionsWhichIncurFees` | `AllowGlobalResourceRestrictedActionsWhichIncurFees` |
| `security-services.yaml` | `ResourceRestrictedActionsWhichIncurNoFees` | `AllowResourceRestrictedActionsWhichIncurNoFees` |
| `data-services.yaml` | `KafkaCluster` | Should follow the standard convention or be merged into existing statements |

---

## 4. Implementation Plan

### Phase 1: Quick Wins -- Tagging Actions (Low Risk)

Move tagging/write actions that take ARNs from unrestricted to resource-restricted
sections. These changes tighten permissions without breaking functionality (the actions
still work, they're just scoped to specific resources).

**Step 1.1: `paas.yaml` (PARTIALLY DONE -- needs correction)**
- [x] Moved `sagemaker:AddTags`, `sagemaker:DeleteTags` to resource-restricted section
- [x] Moved `sagemaker:Describe*` to unrestricted section
- [ ] `sagemaker:ListTags` was placed in resource-restricted but should be in
  unrestricted -- it is a read-only action. Move it to the unrestricted section
  alongside `sagemaker:List*` (or it is already covered by `sagemaker:List*` if
  that wildcard is used)

**Step 1.2: `security-services.yaml`**
- Move `iam:Tag*`, `iam:Untag*` from `GlobalUnrestrictedResourceActionsWhichIncurNoFees`
  to `ResourceRestrictedActionsWhichIncurNoFees`
- The existing Resource block already has `arn:aws:iam::{{ aws_account_id }}:role/ansible-test-*`
  and related IAM ARN patterns
- Verify: do tests tag IAM users? If so, add
  `arn:aws:iam::{{ aws_account_id }}:user/ansible-test-*` to the Resource block
- Move `kms:TagResource`, `kms:UntagResource` to resource-restricted
- Add `arn:aws:kms:{{ aws_region }}:{{ aws_account_id }}:key/*` to the Resource block
  if not already present (currently only `key/ansible-test-*` exists -- may need
  `alias/*` too)

**Step 1.3: `application-services.yaml`**
- Move `ssm:AddTagsToResource`, `ssm:RemoveTagsFromResource` from
  `AllowGlobalUnrestrictedResourceActionsWhichIncurNoFees` to
  `AllowGlobalResourceRestrictedActionsWhichIncurNoFees`
- The existing Resource block already has SSM ARN patterns

**Step 1.4: `application-security.yaml`**
- Move `waf:TagResource`, `waf:UntagResource` to resource-restricted
  - **Caveat**: WAF classic (v1) does not support resource-level permissions for most
    actions. However, `waf:TagResource` and `waf:UntagResource` DO support resource-level
    permissions. These can be restricted even though other WAF classic actions cannot.
  - If creating a new resource-restricted statement, use
    `arn:aws:waf::{{ aws_account_id }}:*` as the resource pattern
- Move `wafv2:TagResource`, `wafv2:UntagResource` to the existing
  `AllowRegionalRestrictedResourceActionsWhichIncurFees` statement (which already
  restricts wafv2 write actions to `arn:aws:wafv2:{{ aws_region }}:{{ aws_account_id }}:*`)

**Step 1.5: `data-services.yaml`**
- Split `KafkaCluster` into two statements:
  - Read-only (`kafka:Describe*`, `kafka:Get*`, `kafka:List*`) -> unrestricted
  - Write actions -> resource-restricted with
    `arn:aws:kafka:{{ aws_region }}:{{ aws_account_id }}:*`
- Move `kafka:TagResource`, `kafka:UntagResource` to the resource-restricted statement

### Phase 2: Read-Only Action Cleanup (Low Risk)

Move over-restricted read-only actions to unrestricted sections. This loosens
permissions slightly but is safe because these actions cannot mutate state.

**Step 2.1: `paas.yaml`**
- Move from resource-restricted to unrestricted:
  - `eks:Describe*`, `eks:List*`
  - `elasticbeanstalk:Describe*`
  - `lightsail:Get*`
  - `lambda:GetAlias`, `lambda:GetFunction`, `lambda:GetFunctionConfiguration`,
    `lambda:GetLayerVersion`, `lambda:GetPolicy`, `lambda:ListLayerVersions`
- After moving, consolidate unrestricted lambda entries:
  - Replace individual `lambda:Get*` entries + `lambda:GetEventSourceMapping` with
    just `lambda:Get*`
  - `lambda:List*` is already there
  - `lambda:Get*` is safe to wildcard -- all 17 Lambda Get actions are read-only
    metadata. `lambda:GetFunction` includes a pre-signed code download URL, but in a
    test account where all functions are test code, this is acceptable.
- `lambda:ListTags` is read-only -- it can move to unrestricted along with other
  lambda List/Get actions (it is already covered by `lambda:List*`)

**Step 2.2: `security-services.yaml`**
- Move from `ResourceRestrictedActionsWhichIncurNoFees` to unrestricted:
  - `acm:Describe*`, `acm:Get*` (safe -- only 2 Get actions, neither exposes secrets)
  - `iam:GetSAMLProvider`, `iam:GetServerCertificate`
- **WARNING: Do NOT consolidate IAM reads to `iam:Get*`.** IAM has 26 Get actions
  including `GetCredentialReport`, `GetAccountAuthorizationDetails`, and
  `GetAccessKeyLastUsed` which expose sensitive account-wide data. Keep individual
  IAM Get actions listed explicitly: `iam:GetRole`, `iam:GetUser`,
  `iam:GetSAMLProvider`, `iam:GetServerCertificate`, `iam:GetInstanceProfile`.
- `iam:GetUser` is currently in a regional unrestricted section -- consider moving it
  to the global unrestricted section alongside the other IAM Get actions for
  consistency (IAM is a global service, the regional condition is unnecessary)

**Step 2.3: `application-services.yaml`**
- Move `logs:Describe*` from resource-restricted to unrestricted
- It consolidates with `logs:List*` already in unrestricted

### Phase 3: Write Action Restriction (Medium Risk)

Move write actions from unrestricted to resource-restricted. These changes tighten
permissions and could break tests if the resource ARN patterns don't cover all
resources the tests create.

**IMPORTANT**: For each change in this phase, run the relevant integration tests to
verify the ARN patterns are correct before merging.

**Step 3.1: `security-services.yaml` -- KMS write actions**
- Move from unrestricted to resource-restricted:
  - `kms:CreateAlias`, `kms:DeleteAlias`
  - `kms:CreateGrant`, `kms:RetireGrant`, `kms:UpdateGrant`
  - `kms:PutKeyPolicy`
  - `kms:UpdateKeyDescription`
  - `kms:Sign`, `kms:Verify`
  - `kms:ScheduleKeyDeletion`
  - `kms:Disable*`, `kms:EnableKey*`
- Resource patterns needed:
  - `arn:aws:kms:{{ aws_region }}:{{ aws_account_id }}:key/*` (broader than
    current `key/ansible-test-*`)
  - `arn:aws:kms:{{ aws_region }}:{{ aws_account_id }}:alias/*`
- Risk: if tests use KMS keys not matching these patterns, they will break
- Mitigation: run KMS-related integration tests, grep for key creation patterns

**Step 3.2: `application-services.yaml` -- SQS/SES/Events write actions**
- Create new resource-restricted statement or add to existing one
- Move SQS write actions (except `CreateQueue`):
  - `sqs:DeleteQueue`, `sqs:SetQueueAttributes`, `sqs:TagQueue`, `sqs:UntagQueue`
  - Resource: `arn:aws:sqs:{{ aws_region }}:{{ aws_account_id }}:*`
- Move SES write actions (except `CreateReceiptRuleSet`):
  - `ses:DeleteIdentity`, `ses:DeleteIdentityPolicy`, `ses:DeleteReceiptRuleSet`,
    `ses:PutIdentityPolicy`, `ses:SetActiveReceiptRuleSet`, `ses:SetIdentity*`,
    `ses:VerifyDomain*`, `ses:VerifyEmailIdentity`
  - Resource: `arn:aws:ses:{{ aws_region }}:{{ aws_account_id }}:identity/*`
- Move Events write actions (except `CreateRule`):
  - `events:DeleteRule`, `events:PutRule`, `events:PutTargets`, `events:RemoveTargets`
  - Resource: `arn:aws:events:{{ aws_region }}:{{ aws_account_id }}:rule/*`
- Risk: SES identity ARN patterns may be different from expected
- Mitigation: check existing tests for resource naming patterns

**Step 3.3: `storage-services.yaml` -- EFS/Backup write actions**
- Move EFS write actions (except `CreateFileSystem`) to resource-restricted:
  - `elasticfilesystem:CreateMountTarget`, `DeleteFileSystem`, `DeleteMountTarget`,
    `CreateTags`, `TagResource`, `UntagResource`, `UpdateFileSystem`,
    `PutLifecycleConfiguration`
  - Resource: `arn:aws:elasticfilesystem:{{ aws_region }}:{{ aws_account_id }}:file-system/*`
- Move Backup write actions (except `CreateBackupPlan`, `CreateBackupVault`) to
  resource-restricted:
  - `backup:CreateBackupSelection`, `DeleteBackupPlan`, `DeleteBackupSelection`,
    `DeleteBackupVault`, `TagResource`, `UntagResource`, `UpdateBackupPlan`
  - Resource: `arn:aws:backup:{{ aws_region }}:{{ aws_account_id }}:backup-plan:*`,
    `arn:aws:backup:{{ aws_region }}:{{ aws_account_id }}:backup-vault:*`

**Step 3.4: `storage-services.yaml` -- ECR write actions**
- Move `ecr:PutImageTagMutability` from unrestricted to resource-restricted
- The `AllowResourceRestrictedActionsWhichIncurNoFees` statement already has
  `arn:aws:ecr:{{ aws_region }}:{{ aws_account_id }}:repository/*` -- add this action there

**Step 3.5: `application-services.yaml` -- SSM `Get*` wildcard split**
- **Pre-existing risk**: `ssm:Get*` is currently wildcarded in the unrestricted section.
  This includes `ssm:GetParameter`, `ssm:GetParameters`, `ssm:GetParametersByPath` which
  can expose secrets stored in SSM Parameter Store (27 total Get actions).
- Split into:
  - Keep safe reads in unrestricted (list individually):
    `ssm:GetAutomationExecution`, `ssm:GetCalendarState`, `ssm:GetCommandInvocation`,
    `ssm:GetConnectionStatus`, `ssm:GetDefaultPatchBaseline`,
    `ssm:GetDeployablePatchSnapshotForInstance`, `ssm:GetDocument`,
    `ssm:GetInventory`, `ssm:GetInventorySchema`, `ssm:GetMaintenanceWindow*`,
    `ssm:GetOpsItem`, `ssm:GetOpsSummary`, `ssm:GetPatchBaseline`,
    `ssm:GetPatchBaselineForPatchGroup`, `ssm:GetServiceSetting`
  - Move sensitive reads to resource-restricted:
    `ssm:GetParameter`, `ssm:GetParameters`, `ssm:GetParametersByPath`,
    `ssm:GetParameterHistory`
  - Resource: `arn:aws:ssm:{{ aws_region }}:{{ aws_account_id }}:parameter/*`
    (already exists in the resource-restricted section)
- Risk: Medium -- tests may rely on `ssm:Get*` wildcard for parameter access. Verify
  that test parameters match the ARN pattern.

**Step 3.6: `storage-services.yaml` -- S3 write actions**
- This is the largest change and highest risk
- Evaluate whether a bucket naming convention exists (e.g., `ansible-test-*`)
- If yes: move all S3 write actions to resource-restricted with
  `arn:aws:s3:::ansible-test-*` and `arn:aws:s3:::ansible-test-*/*`
- If no: document the exception and leave S3 unrestricted, or establish a naming
  convention first
- Risk: S3 bucket names are globally unique; tests may use varied naming
- Mitigation: grep all integration tests for S3 bucket name patterns

### Phase 4: Cost Reclassification (No Permission Change)

Move actions between NoFees and IncurFees sections. These changes do not modify the
actual IAM permissions -- they only improve the accuracy of the organizational
categories.

**Step 4.1: `data-services.yaml` -- RDS fee-incurring actions**
- Create `AllowGlobalResourceRestrictedActionsWhichIncurFees` statement (or add to
  existing)
- Move from NoFees to IncurFees:
  - `rds:CreateDBInstance`
  - `rds:CreateDBInstanceReadReplica`
  - `rds:RestoreDBInstanceFromDBSnapshot`
  - `rds:RestoreDBInstanceFromS3`
  - `rds:RestoreDBInstanceToPointInTime`
  - `rds:RestoreDBClusterFromS3`
  - `rds:RestoreDBClusterFromSnapshot`
  - `rds:RestoreDBClusterToPointInTime`
  - `rds:StartDBInstance`
  - `rds:StartDBCluster`
  - `rds:StartExportTask`
- Resource: same RDS ARN patterns already in use

### Phase 5: Naming Standardization (No Permission Change)

Rename Sids to follow the standard convention. This is purely cosmetic but improves
consistency and readability.

**Step 5.1: `security-services.yaml`**
- `RegionalUnrestrictedResourceActionsWhichIncurNoFees`
  -> `AllowRegionalUnrestrictedResourceActionsWhichIncurNoFees`
- `RegionalUnrestrictedResourceActionsWhichIncurFees`
  -> `AllowRegionalUnrestrictedResourceActionsWhichIncurFees`
- `GlobalUnrestrictedResourceActionsWhichIncurNoFees`
  -> `AllowGlobalUnrestrictedResourceActionsWhichIncurNoFees`
- `GlobalRestrictedResourceActionsWhichIncurFees`
  -> `AllowGlobalResourceRestrictedActionsWhichIncurFees`
- `ResourceRestrictedActionsWhichIncurNoFees`
  -> `AllowResourceRestrictedActionsWhichIncurNoFees`

**Step 5.2: `data-services.yaml`**
- `KafkaCluster` -> merge into standard-named statements (done as part of Phase 1)

---

## 5. Risk Assessment

| Phase | Risk Level | Reason | Mitigation |
|-------|------------|--------|------------|
| Phase 1 (Tagging) | **Low** | Tightening permissions on tag operations. If tests tag resources matching the ARN patterns, nothing breaks. | Verify ARN patterns cover test resources. |
| Phase 2 (Read-only) | **Low** | Loosening permissions on read-only ops. Cannot break tests; only grants broader read access. | Review for sensitive read actions before moving. |
| Phase 3 (Write) | **Medium** | Tightening permissions on write operations. Tests will break if resource ARN patterns don't cover all resources. | Run full integration test suite for each service after changes. Implement incrementally per service. |
| Phase 4 (Cost) | **None** | Reorganization only; no permission changes. | N/A |
| Phase 5 (Naming) | **None** | Sid rename only; no permission changes. IAM does not enforce Sid uniqueness or naming. | N/A |

---

## 6. Implementation Order Recommendation

Combine phases by file rather than by type. This minimizes the number of PRs and avoids
touching the same file in multiple PRs. Each PR should cover one file and include ALL
applicable phases (tagging, read-only, write, cost, naming) for that file.

**Recommended PR order (one PR per file):**

1. **`security-services.yaml`** (Phases 1+2+3+5)
   - Fix Sid naming (Phase 5 -- no permission change, safe to bundle)
   - Move `acm:Describe*`, `acm:Get*` to unrestricted (Phase 2 -- low risk)
   - Move `iam:GetSAMLProvider`, `iam:GetServerCertificate` to unrestricted (Phase 2)
   - Move `iam:Tag*`, `iam:Untag*` to resource-restricted (Phase 1 -- low risk)
   - Move `kms:TagResource`, `kms:UntagResource` to resource-restricted (Phase 1)
   - Move KMS write actions to resource-restricted (Phase 3 -- medium risk, test after)
   - **Do NOT wildcard `iam:Get*`** -- list individual safe actions explicitly

2. **`application-services.yaml`** (Phases 1+2+3)
   - Move `ssm:AddTagsToResource`, `ssm:RemoveTagsFromResource` to restricted (Phase 1)
   - Move `logs:Describe*` to unrestricted (Phase 2)
   - Split `ssm:Get*` wildcard: keep safe reads unrestricted, move `ssm:GetParameter*`
     to resource-restricted (Phase 3 -- pre-existing security risk)
   - Move SQS/SES/Events write actions to resource-restricted (Phase 3 -- test after)
   - Remove dead `events:CreateRule` action (not a real IAM action)

3. **`data-services.yaml`** (Phases 1+4+5)
   - Split `KafkaCluster` into standard-named statements (Phase 1+5)
   - Move RDS fee-incurring actions to IncurFees section (Phase 4)

4. **`storage-services.yaml`** (Phases 1+3)
   - Move EFS/Backup tagging and write actions to resource-restricted (Phase 1+3)
   - Move `ecr:PutImageTagMutability` to resource-restricted (Phase 3)
   - Evaluate S3 naming convention before touching S3 actions (Phase 3 -- highest risk)

5. **`paas.yaml`** (Phase 2)
   - Move read-only actions to unrestricted (eks, elasticbeanstalk, lightsail, lambda)
   - Safe to wildcard `lambda:Get*` and `lambda:List*`

6. **`application-security.yaml`** (Phase 1)
   - Move `waf:TagResource`, `waf:UntagResource` to resource-restricted (WAF classic
     does support resource-level permissions for tag actions specifically)
   - Move `wafv2:TagResource`, `wafv2:UntagResource` to existing wafv2 restricted
     statement

7. **`compute.yaml`** and **`networking.yaml`** -- no changes needed (already well
   organized)

Within each PR: deploy the updated policy, run integration tests for affected services,
fix any ARN pattern issues before merging.

---

## 7. Validating Changes

For any permission change (Phases 1-3), follow this process:

1. Make the policy change in the YAML file
2. Deploy the updated policy to the test account
3. Run the relevant integration tests:
   - `ansible-test integration <target_name> --remote aws`
4. If tests pass, the ARN patterns are correct
5. If tests fail with `AccessDenied`, check:
   - Is the resource ARN pattern correct?
   - Does the test create resources with names matching the pattern?
   - Is there a missing ARN pattern that needs to be added?
6. Fix the ARN pattern and re-test

---

## 8. Appendix: Files and Their Current Statement Structure

### paas.yaml
```
AllowResourceRestrictedActionsWhichIncurFees           Resource: specific ARNs
AllowResourceRestrictedActionsWhichIncurNoFees         Resource: specific ARNs
AllowUnrestrictedResourceActionsWhichIncurFees          Resource: "*"
AllowUnrestrictedResourceActionsWhichIncurNoFees        Resource: "*"
AllowLambdaEventSourceMappings                          Resource: "*" + Condition
AllowGlobalUnrestrictedResourceActionsWhichIncurFees    Resource: "*"
AllowGlobalUnrestrictedResourceActionsWhichIncurNoFees  Resource: "*"
AllowGlobalRestrictedResourceActionsWhichIncurFees      Resource: specific ARNs
```

### compute.yaml
```
AllowRunInstancesInstanceType                                   Resource: specific ARNs + Condition
AllowEc2RunInstances                                            Resource: specific ARNs
AllowRegionalUnrestrictedResourceActionsWhichIncurNoFees        Resource: "*" + ec2:Region
AllowGlobalUnrestrictedResourceActionsWhichIncurFees            Resource: "*" + Condition
AllowGlobalUnrestrictedResourceActionsWhichIncurNoFees          Resource: "*"
AllowGlobalRestrictedResourceActionsWhichIncurFees              Resource: specific ARNs
AllowGlobalResourceRestrictedActionsWhichIncurNoFees            Resource: specific ARNs
```

### networking.yaml
```
AllowGlobalUnrestrictedResourceActionsWhichIncurNoFees          Resource: "*"
AllowRegionalUnrestrictedResourceActionsWhichIncurNoFees        Resource: "*" + ec2:Region
AllowRegionalRestrictedResourceActionsWhichIncurNoFees          Resource: specific ARNs
AllowRegionalRestrictedResourceActionsWhichIncurFees            Resource: specific ARNs
AllowGlobalResourceRestrictedActionsWhichIncurNoFees            Resource: specific ARNs
AllowNATGatewayServiceLinkedRole                                Resource: specific ARNs + Condition
```

### data-services.yaml
```
AllowGlobalUnrestrictedResourceActionsWhichIncurNoFees          Resource: "*"
AllowGlobalResourceRestrictedActionsWhichIncurNoFees            Resource: specific ARNs
AllowGlobalRestrictedResourceActionsWhichIncurFees              Resource: specific ARNs
AllowServiceLinkedRoleCreation                                  Resource: specific ARNs + Condition
KafkaCluster                                                    Resource: "*"
```

### storage-services.yaml
```
AllowGlobalUnrestrictedResourceActionsWhichIncurNoFees          Resource: "*"
AllowGlobalUnrestrictedResourceActionsWhichIncurFees            Resource: "*"
AllowRegionalRestrictedResourceActionsWhichIncurFees            Resource: "*" + aws:RequestedRegion
AllowRegionalRestrictedResourceActionsWhichIncurNoFees          Resource: specific ARNs
AllowResourceRestrictedActionsWhichIncurFees                    Resource: specific ARNs
AllowResourceRestrictedActionsWhichIncurNoFees                  Resource: specific ARNs
```

### application-services.yaml
```
AllowGlobalUnrestrictedResourceActionsWhichIncurNoFees          Resource: "*"
AllowGlobalResourceRestrictedActionsWhichIncurNoFees            Resource: specific ARNs
AllowGlobalRestrictedResourceActionsWhichIncurFees              Resource: specific ARNs
PermitReadOnlyThirdParty                                        Resource: specific ARNs
```

### application-security.yaml
```
AllowRegionalRestrictedResourceActionsWhichIncurFees            Resource: specific ARNs
AllowRegionalUnrestrictedResourceActionsWhichIncurNoFees        Resource: "*" + aws:RequestedRegion
```

### security-services.yaml
```
AssumeRoleTestsAttachAndDetachPolicy                            Resource: specific ARNs + Condition
RegionalUnrestrictedResourceActionsWhichIncurNoFees             Resource: "*" + aws:RequestedRegion
RegionalUnrestrictedResourceActionsWhichIncurFees               Resource: "*" + aws:RequestedRegion
GlobalUnrestrictedResourceActionsWhichIncurNoFees               Resource: "*"
GlobalRestrictedResourceActionsWhichIncurFees                   Resource: specific ARNs
ResourceRestrictedActionsWhichIncurNoFees                       Resource: specific ARNs
ServiceLinkedRoleCreation                                       Resource: specific ARNs + Condition
```
