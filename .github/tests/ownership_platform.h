#import <Cocoa/Cocoa.h>
#import <CoreServices/CoreServices.h>

// Keep the real dispatcher but never query the user's type registry or UI.
@interface OwnershipWorkspace : NSObject
+ (OwnershipWorkspace *)sharedWorkspace;
- (NSString *)localizedDescriptionForType:(NSString *)type;
@end
extern NSString *ownershipDescription;
CFStringRef ownershipType(CFStringRef, CFStringRef, CFStringRef);
#define NSWorkspace OwnershipWorkspace
#define UTTypeCreatePreferredIdentifierForTag ownershipType
