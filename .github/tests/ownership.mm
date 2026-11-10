#include "4DPlugin-Get-file-description.h"
#include "4DPlugin-JSON.h"
#include "ARRAY_TEXT.h"
#include "C_BLOB.h"
#include "C_LONGINT.h"
#include "PrivateTypes.h"
#include "EntryPoints.h"
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>

using Text = std::basic_string<PA_Unichar>;
static std::map<PA_Unichar *, size_t> strings;
static std::map<PA_Handle, size_t> handles;
static std::map<PA_Picture, int> pictures;
struct Ref { int owners = 1; std::map<Text, PA_Variable> values; };
static std::map<Ref *, int> refs;
static bool nullEmpty, failGetter, failHandle;
static int stringifyMode, stringReads, clears;
static Text commandText;
NSString *ownershipDescription;

@implementation OwnershipWorkspace
+ (OwnershipWorkspace *)sharedWorkspace {
    static OwnershipWorkspace *workspace = [[OwnershipWorkspace alloc] init];
    return workspace;
}
- (NSString *)localizedDescriptionForType:(NSString *)type {
    (void)type;
    return ownershipDescription;
}
@end
CFStringRef ownershipType(CFStringRef kind, CFStringRef extension, CFStringRef parent) {
    (void)kind; (void)extension; (void)parent;
    return (CFStringRef)[@"synthetic.type" retain];
}

static void check(bool valid, const char *message) {
    if(!valid) throw std::runtime_error(message);
}
static Text text(const PA_Unichar *p) { return p ? Text(p) : Text(); }
static PA_Unistring makeString(const Text &value) {
    PA_Unistring result = {};
    if(value.empty() && nullEmpty) return result;
    size_t bytes = (value.size() + 1) * sizeof(PA_Unichar);
    result.fString = static_cast<PA_Unichar *>(malloc(bytes));
    check(result.fString != nullptr, "fixture string allocation");
    memcpy(result.fString, value.c_str(), bytes);
    result.fLength = value.size();
    PA_Unichar *pointer = result.fString;
    strings.emplace(pointer, bytes);
    return result;
}
static void readString(PA_Unistring value, const Text &expected) {
    check(value.fLength == static_cast<PA_long32>(expected.size()), "exact UTF16 length");
    if(!value.fString) { check(expected.empty(), "null only for empty"); return; }
    PA_Unichar *pointer = value.fString;
    check(strings.count(pointer) == 1, "read string owner alive");
    check(strings.at(pointer) >= (expected.size()+1)*sizeof(PA_Unichar),
          "UTF16 capacity includes terminator");
    check(Text(value.fString, value.fLength) == expected, "exact UTF16 content");
    check(value.fString[value.fLength] == 0, "UTF16 terminator");
}
static void disposeString(PA_Unistring value) {
    if(!value.fString) return;
    PA_Unichar *pointer = value.fString;
    check(strings.erase(pointer) == 1, "string disposed exactly once");
    free(value.fString);
}
static Ref *newRef() {
    Ref *r = new Ref;
    refs.emplace(r, 1);
    return r;
}
static void clear(PA_Variable *);
static void release(Ref *r) {
    if(!r) return;
    check(refs.count(r) == 1, "reference alive");
    if(--r->owners) return;
    for(auto &entry : r->values) clear(&entry.second);
    refs.erase(r);
    delete r;
}
static PA_Variable copy(PA_Variable value) {
    switch(value.fType) {
        case eVK_Unistring:
            readString(value.uValue.fString, text(value.uValue.fString.fString));
            value.uValue.fString = makeString(text(value.uValue.fString.fString));
            break;
        case eVK_Object:
        case eVK_Collection: {
            Ref *r = static_cast<Ref *>(value.uValue.fObject);
            if(r) { check(refs.count(r) == 1, "retain live ref"); ++r->owners; }
            break;
        }
        case eVK_Picture: {
            PA_Picture p = value.uValue.fPicture;
            if(p) {
                check(pictures.count(p) == 1, "retain live picture");
                ++pictures.at(p);
            }
            break;
        }
        default: break;
    }
    return value;
}
static void clear(PA_Variable *value) {
    ++clears;
    switch(value->fType) {
        case eVK_Unistring: disposeString(value->uValue.fString); break;
        case eVK_Object:
        case eVK_Collection: release(static_cast<Ref *>(value->uValue.fObject)); break;
        case eVK_Picture: {
            PA_Picture p = value->uValue.fPicture;
            if(p) {
                check(pictures.count(p) == 1, "clear live picture");
                if(--pictures.at(p) == 0) { pictures.erase(p); delete static_cast<int *>(p); }
            }
            break;
        }
        case eVK_ArrayUnicode: {
            PA_Handle h = value->uValue.fArray.fData;
            if(h) {
                check(handles.count(h) == 1, "clear live array handle");
                for(int i = 0; i <= value->uValue.fArray.fNbElements; ++i)
                    disposeString(reinterpret_cast<PA_Unistring *>(*h)[i]);
                free(*h); free(h); handles.erase(h);
            }
            break;
        }
        case eVK_Undefined: case eVK_Null: case eVK_Real:
        case eVK_Boolean: case eVK_Longint: break;
        default: throw std::runtime_error("invalid/failed variable must not be cleared");
    }
    value->fType = eVK_Undefined;
}
static void engine(short selector, EngineBlock *eb) {
    switch(selector) {
        case EX_CREATE_UNISTRING:
            eb->fUniString1 = makeString(text(reinterpret_cast<PA_Unichar *>(eb->fHandle)));
            break;
        case EX_SET_UNISTRING: {
            Text content = text(reinterpret_cast<PA_Unichar *>(eb->fHandle));
            disposeString(eb->fUniString1);
            eb->fUniString1 = makeString(content);
            break;
        }
        case EX_DISPOSE_UNISTRING: disposeString(eb->fUniString1); break;
        case EX_VARIABLE_TO_STRING: {
            ++stringReads;
            PA_Variable *v = reinterpret_cast<PA_Variable *>(eb->fHandle);
            check(v->fType == eVK_Unistring, "invalid sentinel must not be read as text");
            readString(v->uValue.fString, text(v->uValue.fString.fString));
            eb->fUniString1 = v->uValue.fString;
            break;
        }
        case EX_CLEAR_VARIABLE: clear(static_cast<PA_Variable *>(eb->fPtr1)); break;
        case EX_CREATE_PICTURE: {
            int *p = new int(0); pictures.emplace(p, 1); eb->fPicture = p; break;
        }
        case EX_DISPOSE_PICTURE: {
            PA_Variable v = {}; PA_SetPictureVariable(&v, eb->fPicture); clear(&v); break;
        }
        case EX_HANDLE_MANAGER: {
            PA_Handle h = eb->fHandle;
            switch(eb->fParam1) {
                case 1:
                    if(failHandle) { failHandle = false; eb->fHandle = nullptr; eb->fError = -108; break; }
                    h = static_cast<PA_Handle>(malloc(sizeof(char *)));
                    *h = static_cast<char *>(calloc(1, eb->fParam2 ? eb->fParam2 : 1));
                    handles.emplace(h, static_cast<size_t>(eb->fParam2)); eb->fHandle = h; break;
                case 2:
                    check(handles.erase(h) == 1, "dispose live handle");
                    free(*h); free(h); break;
                case 3: {
                    check(handles.count(h) == 1, "resize live handle");
                    size_t old = handles.at(h), size = eb->fParam2;
                    *h = static_cast<char *>(realloc(*h, size ? size : 1));
                    if(size > old) memset(*h+old, 0, size-old);
                    handles.at(h) = size; break;
                }
                case 4: eb->fParam2 = handles.at(h); break;
                case 5: eb->fParam3 = reinterpret_cast<sLONG_PTR>(*h); break;
                case 6: case 7: case 8: break;
                default: throw std::runtime_error("unexpected handle operation");
            }
            break;
        }
        case EX_GET_OBJ_VALUE: {
            PA_Variable *out = static_cast<PA_Variable *>(eb->fPtr2);
            if(failGetter) {
                // Failed outputs are not valid variables, even if some bytes look familiar.
                memset(out, 0xa5, sizeof(*out)); eb->fError = -1; break;
            }
            Ref *r = static_cast<Ref *>(eb->fPtr1);
            check(refs.count(r) == 1, "getter ref alive");
            *out = copy(r->values.at(text(eb->fUniString1.fString)));
            break;
        }
        case EX_SET_OBJ_VALUE: {
            Ref *r = static_cast<Ref *>(eb->fPtr1);
            Text key = text(eb->fUniString1.fString);
            PA_Variable v = copy(*static_cast<PA_Variable *>(eb->fPtr2));
            auto old = r->values.find(key);
            if(old != r->values.end()) clear(&old->second);
            r->values[key] = v;
            break;
        }
        case EX_EXECUTE_COMMAND_BY_ID: {
            PA_Variable **args = static_cast<PA_Variable **>(eb->fPtr1);
            PA_Variable *out = static_cast<PA_Variable *>(eb->fPtr2);
            switch(eb->fParam1) {
                case 1231: {
                    Ref *r = static_cast<Ref *>(args[0]->uValue.fObject);
                    PA_SetBooleanVariable(out, r->values.count(text(args[1]->uValue.fString.fString)));
                    break;
                }
                case 1225: {
                    Ref *from = static_cast<Ref *>(args[0]->uValue.fObject), *to = newRef();
                    for(auto &p : from->values) to->values.emplace(p.first, copy(p.second));
                    PA_SetObjectVariable(out, to);
                    // Fail the following Stringify call's parameter handle, not OB Copy.
                    if(stringifyMode == 1) failHandle = true;
                    break;
                }
                case 1217:
                    if(stringifyMode == 2) { PA_SetObjectVariable(out, newRef()); break; }
                    out->fType = eVK_Unistring; out->uValue.fString = makeString(commandText);
                    if(stringifyMode == 3) eb->fError = -1;
                    break;
                default: throw std::runtime_error("unexpected command");
            }
            break;
        }
        default: throw std::runtime_error("unexpected engine selector");
    }
}
static Text fixture(int index) {
    static const PA_Unichar ascii[] = {'A','S','C','I','I',0};
    static const PA_Unichar bmp[] = {0x65e5,0x672c,0x00e9,0};
    static const PA_Unichar supplementary[] = {'A',0xd83d,0xde00,'Z',0};
    static const PA_Unichar empty[] = {0};
    const PA_Unichar *all[] = {ascii, bmp, supplementary, empty};
    return Text(all[index]);
}
static std::string utf8(const Text &s) {
    NSString *value = [[NSString alloc] initWithCharacters:s.c_str() length:s.size()];
    std::string out([value UTF8String]); [value release]; return out;
}
static void balanced() {
    check(strings.empty(), "string balance (initial empty or getter result leaked)");
    check(handles.empty(), "handle balance");
    check(pictures.empty(), "picture balance (initial empty leaked)");
    check(refs.empty(), "object/collection reference balance");
}
static void setters(int which) {
    for(int i = 0; i < 4; ++i) {
        Ref *r = newRef(); Text t = fixture(i); std::string u8 = utf8(t);
        NSString *s = [[NSString alloc] initWithCharacters:t.c_str() length:t.size()];
        const wchar_t *wide = reinterpret_cast<const wchar_t *>([s cStringUsingEncoding:NSUTF32LittleEndianStringEncoding]);
        switch(which) {
            case 0: ob_set_s(r, "key", u8.c_str()); break;
            case 1: ob_set_s(r, L"key", u8.c_str()); break;
            case 2: ob_set_a(r, L"key", wide); break;
            case 3: ob_set_a(r, L"key", &t); break;
        }
        [s release];
        readString(r->values.begin()->second.uValue.fString, t);
        release(r); balanced();
    }
}
static void getters(int which) {
    for(int i = 0; i < 4; ++i) {
        Ref *r = newRef(); Text t = fixture(i);
        PA_Variable v = {}; v.fType = eVK_Unistring; v.uValue.fString = makeString(t);
        r->values[Text{'k'}] = v;
        CUTF8String result;
        switch(which) {
            case 0:
                check(ob_get_a(r, L"k", &result), "existing text property");
                check(std::string(result.begin(), result.end()) == utf8(t), "getter exact UTF8"); break;
            case 1: check(!ob_get_b(r, L"k"), "bool mismatch"); break;
            case 2: check(ob_get_n(r, L"k") == 0, "number mismatch"); break;
            case 3: check(!ob_get_o(r, L"k"), "object mismatch"); break;
            case 4: check(!ob_get_c(r, L"k"), "collection mismatch"); break;
        }
        readString(v.uValue.fString, t); release(r); balanced();
    }
}
static void handoffs() {
    Ref *root = newRef(), *child = newRef(), *col = newRef();
    PA_Variable v = {}; PA_SetObjectVariable(&v, child); root->values[Text{'o'}] = v;
    PA_SetCollectionVariable(&v, col); root->values[Text{'c'}] = v;
    PA_ObjectRef o = ob_get_o(root, L"o");
    PA_CollectionRef c = ob_get_c(root, L"c");
    release(root);
    check(refs.count(static_cast<Ref *>(o)) && refs.count(static_cast<Ref *>(c)), "owning handoff survives parent");
    PA_DisposeObject(o); PA_DisposeCollection(c); balanced();
}
static void scalarGetters() {
    Ref *r = newRef();
    PA_Variable b = {}, n = {};
    PA_SetBooleanVariable(&b, true); PA_SetRealVariable(&n, 123.5);
    r->values[Text{'b'}] = b; r->values[Text{'n'}] = n;
    check(ob_get_b(r,L"b") && ob_get_n(r,L"n") == 123.5, "matching scalar getters");
    CUTF8String unchanged(reinterpret_cast<const uint8_t *>("unchanged"));
    check(ob_get_a(r,L"b",&unchanged), "existing mismatched property remains defined");
    check(std::string(unchanged.begin(),unchanged.end()) == "unchanged", "mismatch preserves text");
    check(!ob_get_a(r,L"missing",&unchanged), "missing property");
    release(r); balanced();
}
static void ownedMismatches() {
    for(int which = 0; which < 5; ++which) {
        Ref *root = newRef(), *child = newRef();
        PA_Variable v = {};
        if(which == 3) PA_SetCollectionVariable(&v, child);
        else PA_SetObjectVariable(&v, child);
        root->values[Text{'k'}] = v;
        CUTF8String output;
        switch(which) {
            case 0: check(ob_get_a(root,L"k",&output), "mismatch still defined"); break;
            case 1: check(!ob_get_b(root,L"k"), "owned bool mismatch"); break;
            case 2: check(ob_get_n(root,L"k") == 0, "owned numeric mismatch"); break;
            case 3: check(!ob_get_o(root,L"k"), "collection is not object"); break;
            case 4: check(!ob_get_c(root,L"k"), "object is not collection"); break;
        }
        check(child->owners == 1, "mismatched getter reference released");
        release(root); balanced();
    }
}
static void failedGetters() {
    Ref *r = newRef(); PA_Variable v = {}; PA_SetBooleanVariable(&v, true);
    r->values[Text{'k'}] = v; failGetter = true;
    CUTF8String output = CUTF8String(reinterpret_cast<const uint8_t *>("unchanged"));
    int before = clears, reads = stringReads;
    check(!ob_get_a(r, L"k", &output), "failed property output rejected before adoption");
    check(!ob_get_b(r, L"k") && ob_get_n(r, L"k") == 0 &&
          !ob_get_o(r, L"k") && !ob_get_c(r, L"k"), "failed getters use documented defaults");
    check(clears == before && stringReads == reads, "failed output neither read nor cleared");
    check(std::string(output.begin(), output.end()) == "unchanged", "failed output preserves text");
    failGetter = false; release(r); balanced();
}
static void stringify(int mode) {
    stringifyMode = mode;
    for(int i = 0; i < 4; ++i) {
        Ref *r = newRef(); commandText = fixture(i);
        CUTF8String output = CUTF8String(reinterpret_cast<const uint8_t *>("unchanged"));
        ob_stringify(r, &output);
        std::string actual(output.begin(), output.end());
        check(actual == (mode ? "unchanged" : utf8(commandText)), "stringify exact result/error preservation");
        release(r); balanced();
    }
}
static void arrays() {
    PA_Variable array = PA_CreateVariable(eVK_ArrayUnicode); PA_ResizeArray(&array, 3);
    for(int i = 0; i < 4; ++i) {
        Text t = fixture(i);
        PA_Unistring owned = PA_CreateUnistring(const_cast<PA_Unichar *>(t.c_str()));
        PA_SetStringInArray(array, i, &owned);
    }
    ARRAY_TEXT wrapper; BytePtr params[] = {reinterpret_cast<BytePtr>(&array)};
    wrapper.fromParamAtIndex(params, 1);
    PA_ClearVariable(&array);
    array = PA_CreateVariable(eVK_ArrayUnicode);
    wrapper.toParamAtIndex(params, 1);
    for(int i = 0; i < 4; ++i) readString(PA_GetStringInArray(array, i), fixture(i));
    PA_Variable other = PA_CreateVariable(eVK_Undefined);
    BytePtr otherParams[] = {reinterpret_cast<BytePtr>(&other)};
    wrapper.toParamAtIndex(otherParams, 1);
    check(PA_GetStringInArray(array, 0).fString != PA_GetStringInArray(other, 0).fString,
          "each output has an independent string allocation");
    wrapper.toParamAtIndex(params, 1);
    PA_ClearVariable(&other);
    PA_Unistring borrowed = PA_GetStringInArray(array, 1);
    PA_Unistring independent = PA_CreateUnistring(borrowed.fString);
    PA_SetStringInArray(array, 1, &independent);
    PA_ResizeArray(&array, 1);
    readString(PA_GetStringInArray(array, 1), fixture(1));
    Text t = fixture(2);
    PA_Unistring rejected = PA_CreateUnistring(const_cast<PA_Unichar *>(t.c_str()));
    PA_Variable wrong = PA_CreateVariable(eVK_Undefined), noData = {};
    noData.fType = eVK_ArrayUnicode;
    PA_SetStringInArray(wrong, 0, &rejected); PA_SetStringInArray(noData, 0, &rejected);
    PA_SetStringInArray(array, -1, &rejected); PA_SetStringInArray(array, 2, &rejected);
    PA_SetStringInArray(array, 1, nullptr);
    readString(rejected, t); PA_DisposeUnistring(&rejected);
    PA_ClearVariable(&array); balanced();
}
static void rejectedArrayOutput() {
    ARRAY_TEXT wrapper;
    Text t = fixture(1);
    wrapper.appendUTF16String(t.c_str());
    PA_Variable noData = {}; noData.fType = eVK_ArrayUnicode;
    BytePtr params[] = {reinterpret_cast<BytePtr>(&noData)};
    bool rejected = false;
    try { wrapper.toParamAtIndex(params, 1); }
    catch(const std::runtime_error &) { rejected = true; }
    balanced();
    check(rejected, "null array handle must report rejection before allocating strings");
}
static void dispatcher() {
    PackInitBlock init = {};
    init.fCall4Dex = engine;
    FourDPackex(kInitPlugin, &init, nullptr, nullptr);
    check(init.fSupportedVersion == 0x00001400 && gCall4D == engine, "actual exported initialization");
    for(int i = 0; i < 4; ++i) {
        Text expected = fixture(i), name{'s','a','m','p','l','e','.','p','d','f'};
        PA_Unistring input = makeString(name), result = makeString(Text{'o','l','d'});
        BytePtr args[] = {reinterpret_cast<BytePtr>(&input)};
        PA_Unistring *resultPtr = &result;
        ownershipDescription = [[NSString alloc] initWithCharacters:expected.c_str() length:expected.size()];
        FourDPackex(1, args, nullptr, &resultPtr);
        [ownershipDescription release]; ownershipDescription = nil;
        std::vector<Text> churn(128, Text(2048, 'x'));
        readString(input, name); readString(result, expected);
        PA_DisposeUnistring(&input); PA_DisposeUnistring(&result); balanced();
    }
}
int main(int argc, char **argv) {
    @autoreleasepool {
        try {
            check(argc == 3, "case and empty representation required");
            nullEmpty = std::string(argv[2]) == "null";
            gCall4D = engine;
            std::string name = argv[1];
            if(name.compare(0,7,"setter-") == 0) setters(std::stoi(name.substr(7)));
            else if(name == "picture-setter") {
                Ref *r = newRef(); PA_Picture p = PA_CreatePicture(nullptr,0);
                ob_set_p(r,L"p",p); release(r); balanced();
            }
            else if(name.compare(0,7,"getter-") == 0) getters(std::stoi(name.substr(7)));
            else if(name == "handoffs") handoffs();
            else if(name == "scalar-getters") scalarGetters();
            else if(name == "owned-mismatches") ownedMismatches();
            else if(name == "failed-getters") failedGetters();
            else if(name.compare(0,10,"stringify-") == 0) stringify(std::stoi(name.substr(10)));
            else if(name == "arrays") arrays();
            else if(name == "array-rejected-output") rejectedArrayOutput();
            else if(name == "dispatcher") dispatcher();
            else throw std::runtime_error("unknown case");
            std::cout << "PASS " << name << " " << argv[2] << std::endl;
        } catch(const std::exception &error) {
            std::cerr << "FAIL " << argv[1] << ": " << error.what() << std::endl;
            return 1;
        }
    }
}
