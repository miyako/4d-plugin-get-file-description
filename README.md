# 4d-plugin-get-file-description
Get the Finder/Explorer description of a file


### Platform

| carbon | cocoa | win32 | win64 |
|:------:|:-----:|:---------:|:---------:|
|<img src="https://cloud.githubusercontent.com/assets/1725068/22371562/1b091f0a-e4db-11e6-8458-8653954a7cce.png" width="24" height="24" />|<img src="https://cloud.githubusercontent.com/assets/1725068/22371562/1b091f0a-e4db-11e6-8458-8653954a7cce.png" width="24" height="24" />|<img src="https://cloud.githubusercontent.com/assets/1725068/22371562/1b091f0a-e4db-11e6-8458-8653954a7cce.png" width="24" height="24" />|<img src="https://cloud.githubusercontent.com/assets/1725068/22371562/1b091f0a-e4db-11e6-8458-8653954a7cce.png" width="24" height="24" />|

```
spctl -a -vv -t install Get file description/Get file description.bundle: accepted
source=Notarized Developer ID
origin=Developer ID Application: keisuke miyako (Y69CWUC25B)
```

### Version

<img src="https://cloud.githubusercontent.com/assets/1725068/18940649/21945000-8645-11e6-86ed-4a0f800e5a73.png" width="32" height="32" /> <img src="https://cloud.githubusercontent.com/assets/1725068/18940648/2192ddba-8645-11e6-864d-6d5692d55717.png" width="32" height="32" />

### Releases

[1.1](https://github.com/miyako/4d-plugin-get-file-description/releases/tag/1.1)

## Syntax

```
description:=Get file description (file)
```

Parameter|Type|Description
------------|------------|----
file|TEXT|the file does not have to exist; only the extension is evaluated
description|TEXT|localised and system dependent

## Examples

```
$description:=Get file description ("sample.txt")
$description:=Get file description ("sample.key")
$description:=Get file description ("sample.pages")
$description:=Get file description ("sample.numbers")
```

<img width="713" alt="2018-05-17 7 22 24" src="https://user-images.githubusercontent.com/1725068/40148120-60c6e8f0-59a7-11e8-9f35-59a71c701fee.png">
