You are transcribing one page of a 19th/20th-century civil or religious vital-records register (births, marriages, deaths, or an alphabetical name index). The page image is the file named in the last line of this message. Read it with your file-reading tool. Do not search the web.

Transcribe literally: keep the original language, script and spelling. Do not translate, modernize or guess from outside knowledge.

Return ONLY a JSON array, one object per register entry (or per index line), with these keys:
- "register_no": entry number as written
- "surname", "given_names": of the main person (child, deceased, groom; for marriages put the bride in other_columns)
- "date_iso": main event date (birth, death or marriage, not circumcision or burial) as YYYY-MM-DD; write unknown digits as X; if two calendars are given, use the later (Gregorian) date
- "date_as_written": the date exactly as written
- "father", "mother": full names as written, or null
- "house_no", "place": as written, or null
- "other_columns": everything else in the row, as plain text

When you are sure of a field, give it as a plain string. When you are not sure, give it as an object:
{"best": "<most likely reading>", "alternatives": ["<up to 3 other plausible readings>"], "reason": "<one short sentence: what evidence you used>"}
Use the page's own evidence to resolve unclear letters: the same name or number written elsewhere in this entry or on this page (a father's surname, a witness, a repeated house number), and names and spellings common in the region and community. Only the first 3 alternatives count.

Write [illegible] for parts you cannot read at all. Use null for empty columns. No commentary outside the JSON.
