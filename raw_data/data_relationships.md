# Webinar Data Relationships & Clay Import Documentation

## Overview
This document explains the relationships between all CSV files in the webinar dataset and how they were combined into the final `webinar_clay_import.csv` file for Clay automation.

## Source Files Summary

| File | Records | Primary Key | Purpose |
|------|---------|-------------|---------|
| `CRM.csv` | 5,000 | `linkedin_url` | Customer/lead database with company info and sales data |
| `registered list.csv` | 1,434 | `BMID` | All webinar registrants with contact info |
| `attend list.csv` | 251 | `BMID` | People who actually attended the webinar |
| `did not attend list.csv` | 1,183 | `BMID` | Registered people who did not attend |
| `poll responses.csv` | 166 | `BMID` | Individual poll responses (multiple per person) |
| `emoji eeaction.csv` | 125 | `BMID` | Emoji reactions given during webinar |
| `Q&A transcript.csv` | 35 | `BMID` | Questions asked during Q&A session |

## Data Quality Issues Resolved

### Duplicates Removed
- **NaN BMID records**: Removed 299+ records across files with missing identifiers
- **Attend list duplicates**: Removed 3 duplicate attendee records
- **Emoji data corruption**: Removed 12 records where same BMID was associated with different people

### Data Integrity Checks
- All remaining records have valid BMID identifiers
- Poll responses correctly show multiple answers per person (avg 1.26 responses/person)
- CRM data successfully matched 100% of registered attendees via LinkedIn URLs

## Join Relationships

### Primary Join: Registration → CRM
```
registered list.BMID → CRM.linkedin_url (via LinkedIn Profile URL)
- Match rate: 100% (1,434/1,434)
- Join type: LEFT JOIN
- Purpose: Enrich registrant data with CRM information
```

### Secondary Joins: Registration → Activity Data
```
registered list.BMID → [attend|did_not_attend].BMID
- Match rate: 100% (all registrants categorized)
- Logic: Attendance status derived from presence in attend/did_not_attend lists
- Result: attendance_status field (registered, attended, did_not_attend)
```

### Aggregated Joins: Multiple Records → Single Summary
```
registered list.BMID → poll responses.BMID (aggregated)
- Aggregation: Pivot table by Question #
- Result fields: poll_q1_brand_visibility, poll_q2_ai_performance
- Multiple responses per person consolidated into single record

registered list.BMID → emoji reactions.BMID (aggregated)
- Aggregation: Sum of emoji counts per person
- Result fields: emoji_😀, emoji_🎉, emoji_😂, emoji_❤️, emoji_😍, emoji_🙌
- Multiple emoji types per person summed together

registered list.BMID → Q&A transcript.BMID (aggregated)
- Aggregation: Concatenate questions, sum upvotes, concatenate answers
- Result fields: qa_questions, qa_total_upvotes, qa_answers
- Multiple questions per person combined with separators
```

## Final Clay Import Schema

### webinar_clay_import.csv Structure
- **Total Records**: 1,413 (all webinar registrants with valid BMIDs)
- **Total Columns**: 54
- **Primary Key**: BMID (unique per person - one row per person)
- **Secondary Key**: linkedin_url (links to CRM)

### Key Fields by Category

#### Identity & Contact
- BMID (primary key)
- Firstname, Lastname
- Email
- LinkedIn Profile URL
- linkedin_url (CRM match)

#### Company Information
- Website Domain
- Industry
- Company LinkedIn URL
- company_name, company_domain (from CRM)
- employees, account_tier (from CRM)

#### Webinar Engagement
- attendance_status (registered/attended/did_not_attend)
- Registration Date/Time
- Duration, Engaged, Chats, Q&A, Polls
- Recording Duration

#### Survey Responses
- Responded to Survey
- Rating, Comment
- Are you tracking your AI search performance?
- Do you measure brand visibility & citations in LLMs?

#### Poll Responses
- poll_q1_brand_visibility ("Do you measure brand visibility & citations in LLMs?")
- poll_q2_ai_performance ("Are you tracking your AI search performance?")

#### Emoji Reactions
- emoji_😀, emoji_🎉, emoji_😂, emoji_❤️, emoji_😍, emoji_🙌

#### Q&A Activity
- qa_questions (semicolon-separated)
- qa_total_upvotes
- qa_answers (semicolon-separated)

#### CRM Sales Data
- customer_status, created_at, last_activity_at
- trial_start_date, trial_end_date
- mrr_eur (Monthly Recurring Revenue in EUR)

## Data Flow for Clay Automation

1. **Import**: `webinar_clay_import.csv` as primary table
2. **Enrichment**: Use BMID to link additional activity data if needed
3. **Segmentation**: Use attendance_status, customer_status, and poll responses for targeting
4. **Scoring**: Combine engagement metrics (Duration, Chats, Polls) with sales data (mrr_eur, account_tier)
5. **Automation Triggers**:
   - High engagement + no CRM match → Lead nurturing
   - Attended + trial ended → Follow-up sequence
   - Low engagement → Re-engagement campaign

## Data Quality Metrics

- **Completeness**: 100% BMID coverage, 100% CRM matching, 98.5% valid LinkedIn URLs
- **Accuracy**: All duplicates removed, data corruption resolved, incomplete URLs cleaned
- **Consistency**: Standardized field names and data types
- **Integrity**: All joins validated, no orphaned records

## Notes for Clay Implementation

1. **BMID as Primary Key**: Use for all person-level operations
2. **LinkedIn URL for CRM Sync**: Use for ongoing CRM data updates
3. **Aggregated Fields**: Poll and emoji data already summarized per person
4. **Multi-value Fields**: Q&A questions/answers use semicolon separators
5. **Date Fields**: Ensure proper date parsing for timestamps
6. **Currency Fields**: mrr_eur is in Euros, handle accordingly

## File Locations
- Source files: `/raw_data/*.csv`
- Final import: `/raw_data/webinar_clay_import.csv`
- Documentation: `/raw_data/data_relationships.md`
