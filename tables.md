
todos
Table name

public
Schema
Row Level Security

Columns
Add column
id
SERIAL
PRIMARY KEY
title
VARCHAR(255)
NOT NULL
description
TEXT
completed
BOOLEAN
NOT NULL
due_at
TIMESTAMP WITH TIME ZONE
created_at
TIMESTAMP WITH TIME ZONE
NOT NULL
DEFAULTnow()

updated_at
TIMESTAMP WITH TIME ZONE
NOT NULL
DEFAULTnow()