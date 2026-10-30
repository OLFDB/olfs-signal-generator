/* SPDX-License-Identifier: Apache-2.0 */
/* Project-only extension: one full-speed, synchronous USB IN stream.
 * The DT-generated alternate 1 is 16-bit. Alternate 2 adds packed 24-bit.
 */
#undef AS_DESCRIPTORS_ARRAYS
#define AS_DESCRIPTORS_ARRAYS(node) \
    OLF_BASE_AS_DESCRIPTORS_ARRAYS(node) \
    BUILD_ASSERT(AS_IS_USB_ISO_IN(node) && AS_IS_SOF_SYNCHRONIZED(node), \
                 "Format extension requires a synchronous IN stream"); \
    BUILD_ASSERT(!UAC2_ALLOWED_AT_HIGH_SPEED(DT_PARENT(node)), "Full-speed only"); \
    BUILD_ASSERT(DT_PROP(node, subslot_size) == 2 && DT_PROP(node, bit_resolution) == 16, \
                 "Base alternate must be 16-bit PCM"); \
    AS_INTERFACE_FS_DESCRIPTOR_ARRAY(node, 2, 1) \
    static uint8_t DESCRIPTOR_NAME(as_format24_desc, node)[] = {6, CS_INTERFACE, 2, 1, 3, 24}; \
    static uint8_t DESCRIPTOR_NAME(fs_std_data_ep24, node)[] = { \
        7, USB_DESC_ENDPOINT, AS_DATA_EP_ADDR(node), AS_DATA_EP_ATTR(node), \
        U16_LE(AUDIO_STREAMING_NUM_SPATIAL_LOCATIONS(node) * 3 * AS_SAMPLES_PER_FRAME(node)), \
        AS_FS_DATA_EP_BINTERVAL(node), \
    };

#undef AS_FS_DESCRIPTORS_PTRS
#define AS_FS_DESCRIPTORS_PTRS(node) \
    OLF_BASE_AS_FS_DESCRIPTORS_PTRS(node) \
    AS_INTERFACE_FS_DESCRIPTOR_PTR(node, 2) \
    (struct usb_desc_header *)&DESCRIPTOR_NAME(as_general_desc, node), \
    (struct usb_desc_header *)&DESCRIPTOR_NAME(as_format24_desc, node), \
    (struct usb_desc_header *)&DESCRIPTOR_NAME(fs_std_data_ep24, node), \
    (struct usb_desc_header *)&DESCRIPTOR_NAME(cs_data_ep, node),

/* Five descriptor pointers are appended for alternate 2. The class's endpoint
 * lookup keeps pointing at alternate 1. Both alternates use the sole ISO-IN
 * hardware endpoint (0x88); send() only uses its address, not its packet size.
 */
#undef UAC2_DESCRIPTOR_AS_DATA_EP_INDEX
#define UAC2_DESCRIPTOR_AS_DATA_EP_INDEX(node) \
    (UAC2_DESCRIPTOR_AS_DESC_END_COUNT(node) - 5 \
     - AS_EXPLICIT_FEEDBACK_ENDPOINT_DESCRIPTOR_COUNT(node) \
     - AS_ISOCHRONOUS_DATA_ENDPOINT_DESCRIPTORS_COUNT(node))

void olf_audio_format_update(uint8_t alternate);
