# Japanese Report Translation Protocol

> Closes TODO_PhaseA: DD-015 EN/JA auto-translation is a credibility risk.
> Version: 1.0.0

---

## The Problem With Machine Translation of Security Findings

Machine translation of cloud security findings into Japanese introduces two
categories of risk:

1. **Technical term mistranslation**: Terms like "Transit Gateway", "Security Group",
   "Network Security Group", "Managed Identity", and "Service Principal" have
   established Japanese usage in the AWS/Azure documentation ecosystem.
   Machine translation will produce inconsistent or incorrect renderings.

2. **Nuance loss in severity language**: Security finding severity language
   ("critical", "high impact", "immediate remediation required") carries legal
   and contractual weight. Incorrect nuance in Japanese can misrepresent severity
   to an executive reader.

---

## Translation Protocol

### Step 1: Automated pre-translation (EN -> JA)
- The report engine produces a machine-translated JA draft using DeepL API
  (not Google Translate — DeepL produces higher-quality technical Japanese).
- The draft is clearly watermarked: 「この翻訳は自動翻訳です。レビュー前に使用しないでください。」

### Step 2: Technical glossary enforcement
The following terms are NEVER machine-translated. They are substituted from
the approved glossary before translation and restored after:

| English Term | Approved Japanese |
|---|---|
| Transit Gateway | Transit Gateway (TGW) |
| Network Security Group | ネットワークセキュリティグループ (NSG) |
| Security Group | セキュリティグループ |
| Virtual Network | 仮想ネットワーク (VNet) |
| Virtual Private Cloud | バーチャルプライベートクラウド (VPC) |
| Managed Identity | マネージドID |
| Service Principal | サービスプリンシパル |
| Landing Zone | ランディングゾーン |
| GuardDuty | Amazon GuardDuty |
| Defender for Cloud | Microsoft Defender for Cloud |

### Step 3: Native speaker review gate
- The JA draft is reviewed by a bilingual cloud engineer or a certified
  Japanese technical translator before delivery.
- This review is **mandatory** — the delivery portal blocks JA report
  publication until the `ja_review_complete` flag is set by the reviewer.
- Review is logged in the engagement audit log with reviewer identity and timestamp.

### Step 4: Client delivery
- Final JA report replaces the draft.
- Watermark is removed.
- Both EN and JA reports are delivered together.

---

## Reviewer Checklist (JA)

- [ ] All technical terms from glossary are correctly applied
- [ ] Severity language is accurate and appropriately formal (敵語体)
- [ ] No machine-translated technical product names remain
- [ ] Executive summary tone is appropriate for C-level Japanese audience
- [ ] All numbers, CIDRs, account IDs, and resource names are unchanged
