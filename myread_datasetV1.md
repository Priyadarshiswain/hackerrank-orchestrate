
| request  table  | audit log  | user identities | system activity | evidence    | deletion rules  | output          |
| --------------- | ---------- | --------------- | --------------- | ----------- | --------------- | --------------- |
| Case Id         | audit id   | userid          | activity id     | evidence id | rule id         | case id         |
| email           | user id    | name            | event time      | file path   | data category   | deletion status |
| requested at    | event time | email           | event type      | origin      | condition       | steps           |
| reported status | field name | phone           | source system   | captured at | required action |                 |
| reported at     | old value  | email hash      | target system   |             |                 |                 |
| audited at      | new value  | updated at      | resource id     |             |                 |                 |
| request text    |            |                 | reported result |             |                 |                 |
|                 |            |                 | details         |             |                 |                 |

Questions
1. requested at in request table is obiously the time when the request was raised, what is audited and reported at , I am bit confused on this and how these impact the output
2. we need to join request and user identies via email (fk). user identies and audot log can be joined via userid, how is auidt log joined to syatem acticvity, I see only event time as one possible cadidate, need to check. I have no idea how evidence table to used.
3. deletion rule table is reference table, but datacategory has no proper definition, need more analysis, 
4. output table needs to be build for each case id, and deletion staus can be one of `COMPLETE`, `INCOMPLETE`, or `NOT_APPLICABLE`
5. step is a json 
6. PII data list : name , email, phone, email hash?? , 