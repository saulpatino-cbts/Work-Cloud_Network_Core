<#
.SYNOPSIS
Bootstraps the AWS identity, IAM, Terraform state backend, and GitHub
secrets/variables required to deploy the CNA platform via the migrate/ IaC.

.DESCRIPTION
This script automates the entire pre-deployment setup:
  1. Creates an IAM OIDC provider for GitHub Actions.
  2. Creates a deploy IAM role with GitHub OIDC trust policy.
  3. Attaches assessment reader policies: ReadOnlyAccess, SecurityAudit,
     AWSBillingReadOnlyAccess (AWS equivalents of Azure's Global Reader,
     Security Reader, Billing Reader).
  4. Attaches write policies for Terraform to manage CNA infrastructure.
  5. Provisions the Terraform remote state backend (S3 bucket + DynamoDB table).
  6. Seeds GitHub secrets and variables so CI/CD workflows can deploy.

Idempotent: safe to re-run. Existing resources are detected and skipped.

.PARAMETER Repo
GitHub repository in owner/name format. Auto-detected from current git remote.

.PARAMETER Environment
Target environment (dev or prod).

.PARAMETER AwsRegion
AWS region for deployment.

.PARAMETER ProjectName
Project name prefix for resource naming.

.EXAMPLE
./migrate/scripts/Initialize-Migration.ps1 -Environment dev -AwsRegion us-east-2
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$Repo,
    [string]$Branch = "main",
    [ValidateSet("dev", "prod")]
    [string]$Environment = "dev",
    [string]$AwsRegion = "us-east-2",
    [string]$ProjectName = "cna",
    [switch]$SkipGitHubSetup
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step { param([string]$M) Write-Host "`n==> $M" -ForegroundColor Cyan }
function Write-Ok { param([string]$M) Write-Host "    [OK] $M" -ForegroundColor Green }
function Write-Warn { param([string]$M) Write-Host "    [!] $M" -ForegroundColor Yellow }
function Write-Info { param([string]$M) Write-Host "    [INFO] $M" -ForegroundColor DarkCyan }

function Assert-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name not found. Install it first."
    }
}

# ─── Prerequisites ────────────────────────────────────────────────────────────
Write-Step "Checking prerequisites"
Assert-Command "aws"
if (-not $SkipGitHubSetup) { Assert-Command "gh" }

# ─── AWS Identity ─────────────────────────────────────────────────────────────
Write-Step "Verifying AWS CLI session"
$callerJson = aws sts get-caller-identity --output json 2>$null
if ($LASTEXITCODE -ne 0) { throw "AWS CLI not authenticated. Run 'aws configure' or set credentials." }
$caller = $callerJson | ConvertFrom-Json
$accountId = $caller.Account
Write-Ok "AWS Account: $accountId ($(($caller.Arn -split '/')[1]))"

# ─── Naming ───────────────────────────────────────────────────────────────────
$namePrefix = "$ProjectName-$Environment"
$roleName = "$namePrefix-github-deploy"
$tfstateBucket = "$namePrefix-tfstate-$accountId"
$tfstateDynamo = "$namePrefix-tfstate-lock"

if (-not $Repo -and -not $SkipGitHubSetup) {
    $Repo = (gh repo view --json nameWithOwner -q .nameWithOwner 2>$null)
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($Repo)) {
        $Repo = Read-Host "GitHub repo (owner/name)"
    }
}
Write-Info "Deploy role: $roleName"
Write-Info "Tfstate bucket: $tfstateBucket"

# ─── OIDC Provider ────────────────────────────────────────────────────────────
Write-Step "Ensuring GitHub Actions OIDC provider"
$oidcArn = "arn:aws:iam::${accountId}:oidc-provider/token.actions.githubusercontent.com"
$existingOidc = aws iam get-open-id-connect-provider --open-id-connect-provider-arn $oidcArn --output json 2>$null
if ($LASTEXITCODE -ne 0) {
    if ($PSCmdlet.ShouldProcess("GitHub OIDC", "create IAM OIDC provider")) {
        aws iam create-open-id-connect-provider `
            --url "https://token.actions.githubusercontent.com" `
            --client-id-list "sts.amazonaws.com" `
            --thumbprint-list "ffffffffffffffffffffffffffffffffffffffff" `
            --output none
        if ($LASTEXITCODE -ne 0) { throw "Failed to create OIDC provider." }
    }
    Write-Ok "Created GitHub OIDC provider"
} else {
    Write-Ok "OIDC provider exists"
}

# ─── Deploy IAM Role ─────────────────────────────────────────────────────────
Write-Step "Ensuring deploy IAM role: $roleName"
$existingRole = aws iam get-role --role-name $roleName --output json 2>$null
if ($LASTEXITCODE -ne 0) {
    $trustPolicy = @{
        Version = "2012-10-17"
        Statement = @(@{
            Effect = "Allow"
            Action = "sts:AssumeRoleWithWebIdentity"
            Principal = @{ Federated = $oidcArn }
            Condition = @{
                StringLike = @{
                    "token.actions.githubusercontent.com:sub" = @(
                        "repo:${Repo}:ref:refs/heads/$Branch",
                        "repo:${Repo}:environment:$Environment"
                    )
                }
                StringEquals = @{
                    "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
                }
            }
        })
    } | ConvertTo-Json -Depth 10 -Compress

    $policyFile = [System.IO.Path]::GetTempFileName()
    try {
        Set-Content -Path $policyFile -Value $trustPolicy -Encoding UTF8
        if ($PSCmdlet.ShouldProcess($roleName, "create IAM role")) {
            aws iam create-role --role-name $roleName --assume-role-policy-document "file://$policyFile" --output none
            if ($LASTEXITCODE -ne 0) { throw "Failed to create IAM role." }
        }
        Write-Ok "Created IAM role: $roleName"
    } finally {
        Remove-Item -Path $policyFile -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 10
} else {
    Write-Ok "IAM role exists: $roleName"
}

# ─── Attach Reader Policies (Global Reader + Security Reader + Billing Reader) ─
Write-Step "Attaching assessment reader policies"
$readerPolicies = @(
    "arn:aws:iam::aws:policy/ReadOnlyAccess",
    "arn:aws:iam::aws:policy/SecurityAudit",
    "arn:aws:iam::aws:policy/AWSBillingReadOnlyAccess"
)

foreach ($policyArn in $readerPolicies) {
    $policyName = ($policyArn -split '/')[-1]
    $attached = aws iam list-attached-role-policies --role-name $roleName --query "AttachedPolicies[?PolicyArn=='$policyArn'].PolicyArn" --output text 2>$null
    if (-not [string]::IsNullOrWhiteSpace($attached)) {
        Write-Ok "Already attached: $policyName"
        continue
    }
    if ($PSCmdlet.ShouldProcess($roleName, "attach $policyName")) {
        aws iam attach-role-policy --role-name $roleName --policy-arn $policyArn
        if ($LASTEXITCODE -ne 0) { throw "Failed to attach $policyName." }
    }
    Write-Ok "Attached: $policyName"
}

# ─── Attach Deploy Write Policy ───────────────────────────────────────────────
Write-Step "Ensuring deploy write policy"
$deployPolicyName = "$namePrefix-deploy-write"
$deployPolicyArn = "arn:aws:iam::${accountId}:policy/$deployPolicyName"

$existingPolicy = aws iam get-policy --policy-arn $deployPolicyArn --output json 2>$null
if ($LASTEXITCODE -ne 0) {
    $deployPolicy = @{
        Version = "2012-10-17"
        Statement = @(
            @{
                Sid = "InfraManagement"
                Effect = "Allow"
                Action = @(
                    "ec2:*", "ecs:*", "elasticloadbalancing:*", "rds:*",
                    "s3:*", "secretsmanager:*", "cloudfront:*", "wafv2:*",
                    "logs:*", "iam:*", "cloudwatch:*", "application-autoscaling:*",
                    "dynamodb:*"
                )
                Resource = "*"
            }
        )
    } | ConvertTo-Json -Depth 5 -Compress

    $policyFile = [System.IO.Path]::GetTempFileName()
    try {
        Set-Content -Path $policyFile -Value $deployPolicy -Encoding UTF8
        if ($PSCmdlet.ShouldProcess($deployPolicyName, "create IAM policy")) {
            aws iam create-policy --policy-name $deployPolicyName --policy-document "file://$policyFile" --output none
            if ($LASTEXITCODE -ne 0) { throw "Failed to create deploy write policy." }
        }
        Write-Ok "Created policy: $deployPolicyName"
    } finally {
        Remove-Item -Path $policyFile -Force -ErrorAction SilentlyContinue
    }
}

$attached = aws iam list-attached-role-policies --role-name $roleName --query "AttachedPolicies[?PolicyArn=='$deployPolicyArn'].PolicyArn" --output text 2>$null
if ([string]::IsNullOrWhiteSpace($attached)) {
    aws iam attach-role-policy --role-name $roleName --policy-arn $deployPolicyArn
    Write-Ok "Attached: $deployPolicyName"
} else {
    Write-Ok "Already attached: $deployPolicyName"
}

# ─── Terraform State Backend (S3 + DynamoDB) ──────────────────────────────────
Write-Step "Provisioning Terraform state backend"

# S3 bucket
$bucketExists = aws s3api head-bucket --bucket $tfstateBucket 2>$null
if ($LASTEXITCODE -ne 0) {
    if ($PSCmdlet.ShouldProcess($tfstateBucket, "create S3 bucket")) {
        if ($AwsRegion -eq "us-east-1") {
            aws s3api create-bucket --bucket $tfstateBucket --region $AwsRegion
        } else {
            aws s3api create-bucket --bucket $tfstateBucket --region $AwsRegion --create-bucket-configuration LocationConstraint=$AwsRegion
        }
        if ($LASTEXITCODE -ne 0) { throw "Failed to create tfstate bucket." }

        aws s3api put-bucket-versioning --bucket $tfstateBucket --versioning-configuration Status=Enabled
        aws s3api put-bucket-encryption --bucket $tfstateBucket --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"aws:kms"},"BucketKeyEnabled":true}]}'
        aws s3api put-public-access-block --bucket $tfstateBucket --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
    }
    Write-Ok "Created tfstate bucket: $tfstateBucket"
} else {
    Write-Ok "Tfstate bucket exists: $tfstateBucket"
}

# DynamoDB lock table
$tableExists = aws dynamodb describe-table --table-name $tfstateDynamo --output json 2>$null
if ($LASTEXITCODE -ne 0) {
    if ($PSCmdlet.ShouldProcess($tfstateDynamo, "create DynamoDB lock table")) {
        aws dynamodb create-table `
            --table-name $tfstateDynamo `
            --attribute-definitions AttributeName=LockID,AttributeType=S `
            --key-schema AttributeName=LockID,KeyType=HASH `
            --billing-mode PAY_PER_REQUEST `
            --region $AwsRegion `
            --output none
        if ($LASTEXITCODE -ne 0) { throw "Failed to create DynamoDB lock table." }
    }
    Write-Ok "Created DynamoDB lock table: $tfstateDynamo"
} else {
    Write-Ok "DynamoDB lock table exists: $tfstateDynamo"
}

# ─── GitHub Secrets & Variables ───────────────────────────────────────────────
if (-not $SkipGitHubSetup) {
    Write-Step "Configuring GitHub secrets and variables"

    $roleArn = "arn:aws:iam::${accountId}:role/$roleName"

    # Ensure GitHub environment
    $envExists = gh api "repos/$Repo/environments/$Environment" --jq '.name' 2>$null
    if ($LASTEXITCODE -ne 0) {
        gh api -X PUT "repos/$Repo/environments/$Environment" | Out-Null
        Write-Ok "Created GitHub environment: $Environment"
    } else {
        Write-Ok "GitHub environment exists: $Environment"
    }

    # Secrets
    $secrets = @{
        AWS_DEPLOY_ROLE_ARN = $roleArn
        AWS_REGION          = $AwsRegion
    }
    foreach ($entry in $secrets.GetEnumerator()) {
        $entry.Value | gh secret set $entry.Key --repo $Repo | Out-Null
        Write-Ok "Set secret: $($entry.Key)"
    }

    # Environment-scoped
    $roleArn | gh secret set AWS_DEPLOY_ROLE_ARN --repo $Repo --env $Environment | Out-Null
    Write-Ok "Set env secret: AWS_DEPLOY_ROLE_ARN (env:$Environment)"

    # Variables
    $variables = @{
        TFSTATE_BUCKET    = $tfstateBucket
        TFSTATE_DYNAMO    = $tfstateDynamo
        TFSTATE_REGION    = $AwsRegion
        CNA_ENVIRONMENT   = $Environment
        AWS_ACCOUNT_ID    = $accountId
    }
    foreach ($entry in $variables.GetEnumerator()) {
        gh variable set $entry.Key --repo $Repo --body $entry.Value | Out-Null
        Write-Ok "Set variable: $($entry.Key) = $($entry.Value)"
    }
}

# ─── Summary ──────────────────────────────────────────────────────────────────
Write-Step "Bootstrap Complete"
Write-Host ""
Write-Host "  AWS Account       : $accountId" -ForegroundColor White
Write-Host "  Region            : $AwsRegion" -ForegroundColor White
Write-Host "  Deploy Role       : arn:aws:iam::${accountId}:role/$roleName" -ForegroundColor White
Write-Host "  Tfstate Bucket    : $tfstateBucket" -ForegroundColor White
Write-Host "  Tfstate Lock Table: $tfstateDynamo" -ForegroundColor White
Write-Host ""
Write-Host "  Policies attached (assessment reader):" -ForegroundColor Cyan
Write-Host "    - ReadOnlyAccess (Global Reader equivalent)" -ForegroundColor White
Write-Host "    - SecurityAudit (Security Reader equivalent)" -ForegroundColor White
Write-Host "    - AWSBillingReadOnlyAccess (Billing Reader equivalent)" -ForegroundColor White
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor Yellow
Write-Host "    1. cd migrate" -ForegroundColor White
Write-Host "    2. terraform init \" -ForegroundColor White
Write-Host "         -backend-config=`"bucket=$tfstateBucket`" \" -ForegroundColor White
Write-Host "         -backend-config=`"key=migrate.tfstate`" \" -ForegroundColor White
Write-Host "         -backend-config=`"region=$AwsRegion`" \" -ForegroundColor White
Write-Host "         -backend-config=`"dynamodb_table=$tfstateDynamo`"" -ForegroundColor White
Write-Host "    3. Set TF_VAR_* for sensitive values (db_password, secrets, etc.)" -ForegroundColor White
Write-Host "    4. terraform plan -out=tfplan" -ForegroundColor White
Write-Host "    5. terraform apply tfplan" -ForegroundColor White
