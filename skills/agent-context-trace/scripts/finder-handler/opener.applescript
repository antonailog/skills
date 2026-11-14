use framework "Foundation"
use scripting additions

-- This protocol only reveals an existing absolute path. It never opens a file.
on open location incomingURL
    try
        set components to current application's NSURLComponents's componentsWithString:incomingURL
        if components is missing value then return
        if (components's |scheme|() as text) is not "agent-context-trace" then return
        if (components's |host|() as text) is not "reveal" then return
        if (components's |path|() as text) is not "" then return
        if components's |user|() is not missing value then return
        if components's |password|() is not missing value then return
        if components's |port|() is not missing value then return
        if components's |fragment|() is not missing value then return
        set queryItems to components's |queryItems|()
        if queryItems is missing value then return
        if (queryItems's |count|() as integer) is not 1 then return
        set queryItem to queryItems's objectAtIndex:0
        if (queryItem's |name|() as text) is not "path" then return
        -- NSURLQueryItem decodes percent-encoded UTF-8 exactly once; + stays +.
        set decodedPath to queryItem's |value|()
        if decodedPath is missing value then return
        if not (decodedPath's hasPrefix:"/") then return
        set pathText to decodedPath as text
        if pathText contains (character id 0) then return
        if not (current application's NSFileManager's defaultManager()'s fileExistsAtPath:decodedPath) then return
        do shell script "/usr/bin/open -R " & quoted form of pathText
    end try
end open location
