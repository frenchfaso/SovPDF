import os
import base64
from pypdf import PdfReader, PdfWriter
from pyscript import when, display, document, fetch, window, ffi

# Add console object for debugging
console = window.console

# Global variables
selected_preset = "medium"  # Changed from "normal" to "medium"
current_pdf = None
current_pdf_size = 0
processed_files = {}  # Store processed files for download
is_processing = False  # Flag to prevent multiple simultaneous processing
temp_files = []  # Track temporary files for cleanup
current_pdf_compressed_files = []  # Track compressed files for the current PDF
current_button = None  # Track the currently clicked button

# Cache frequently accessed DOM elements
DOM_ELEMENTS = {}

def get_element(selector):
    """Get DOM element with caching for better performance"""
    if selector not in DOM_ELEMENTS:
        DOM_ELEMENTS[selector] = document.querySelector(selector)
    return DOM_ELEMENTS[selector]

def highlight_selected_button(button_id):
    # Remove active class from all buttons
    get_element("#mediumButton").classList.remove("is-active")  # Changed from normalButton to mediumButton
    get_element("#smallButton").classList.remove("is-active")
    get_element("#tinyButton").classList.remove("is-active")
    
    # Add active class to selected button
    get_element(f"#{button_id}").classList.add("is-active")

def set_button_loading(button_id, is_loading=True):
    """Set the loading state of a button"""
    button = get_element(f"#{button_id}")
    if is_loading:
        button.classList.add("is-loading")
    else:
        button.classList.remove("is-loading")

# Clean up temporary files
def cleanup_files(event=None, keep_current=False):
    global temp_files
    console.log(f"Cleaning up {len(temp_files)} temporary files")
    
    files_to_keep = current_pdf_compressed_files if keep_current else []
    
    for file_path in temp_files:
        try:
            if os.path.exists(file_path) and file_path not in files_to_keep:
                os.remove(file_path)
                console.log(f"Removed temporary file: {file_path}")
        except Exception as e:
            console.error(f"Error removing file {file_path}: {str(e)}")
    
    # Update the list to only contain files we kept
    if keep_current:
        temp_files = files_to_keep.copy()
    else:
        temp_files = []
        # Also clear the current PDF compressed files list
        current_pdf_compressed_files.clear()

def reduce_quality(reader, quality=90):
    console.log(f"Reducing quality with setting: {quality}")
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    for page in writer.pages:
        for img in page.images:
            img.replace(img.image, quality=quality)
    
    writer.add_metadata(reader.metadata)
    console.log("Quality reduction complete")
    return writer

def compress_lossless(writer, level=3):
    console.log(f"Compressing with level: {level}")
    for page in writer.pages:
        page.compress_content_streams(level=level)  # This is CPU intensive!

    console.log("Compression complete")
    return writer

# Function to safely handle filenames with special characters
def safe_filename(filename):
    # Replace any potentially problematic characters
    unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    return filename

# Function to prepare a file for download
def prepare_file_for_download(filepath):
    try:
        with open(filepath, "rb") as f:
            content = f.read()
            
        # Convert to base64 for easier handling
        b64content = base64.b64encode(content).decode('utf-8')
        
        # Generate a unique ID for this download
        download_id = f"download_{len(processed_files)}"
        
        # Register the download with JavaScript - using a single global download function
        js_code = f"""
        if (!window.sovPdfDownload) {{
            window.sovPdfDownload = function(data, filename) {{
                const link = document.createElement('a');
                link.href = data;
                link.download = filename;
                document.body.appendChild(link);
                link.click();
                setTimeout(function() {{
                    document.body.removeChild(link);
                }}, 100);
            }};
        }}
        """
        
        # Execute the JavaScript code only once
        if not hasattr(window, "sovPdfDownloadRegistered"):
            script = document.createElement('script')
            script.textContent = js_code
            document.head.appendChild(script)
            window.sovPdfDownloadRegistered = True
        
        # Store the base64 data for download
        processed_files[download_id] = {
            'filename': os.path.basename(filepath),
            'data': f"data:application/pdf;base64,{b64content}"
        }
        
        return download_id
    except Exception as e:
        console.error(f"Error preparing file for download: {str(e)}")
        return None

async def process_pdf(filename, preset):
    """Process the PDF with the selected preset"""
    global is_processing, temp_files, current_pdf_compressed_files, current_button
    
    # Prevent multiple processing
    if is_processing:
        console.log("Already processing a PDF, please wait")
        # Show user notification
        show_notification("Please wait for the current processing to finish", "is-warning")
        return False
        
    is_processing = True
    button_id = f"{preset}Button"
    current_button = button_id
    
    # Set button to loading state
    set_button_loading(button_id, True)
    
    try:
        # Get friendly name for display
        preset_display_name = preset.capitalize()
        console.log(f"Processing {filename} with preset {preset_display_name}")
        
        # Map presets to quality and level
        presets = {
            "medium": (90, 3),
            "small": (75, 5),
            "tiny": (50, 9)
        }

        quality, level = presets[preset]
        console.log(f"Using quality={quality}, level={level}")

        reader = PdfReader(filename)
        console.log(f"PDF has {len(reader.pages)} pages")
        writer = reduce_quality(reader, quality)
        writer = compress_lossless(writer, level)
        
        # Create safe output filename with preset name
        base_name = os.path.splitext(os.path.basename(filename))[0]
        safe_base_name = safe_filename(base_name)
        compressed_filename = f"{safe_base_name}-{preset}.pdf"
        
        console.log(f"Writing compressed file: {compressed_filename}")
        
        with open(compressed_filename, "wb") as f:
            writer.write(f)
            
        # Add file to cleanup list
        temp_files.append(compressed_filename)
        
        # Also add to the current PDF compressed files list
        if compressed_filename not in current_pdf_compressed_files:
            current_pdf_compressed_files.append(compressed_filename)

        compressed_size = os.path.getsize(compressed_filename) / 1024
        original_size = current_pdf_size
        compression_ratio = compressed_size / original_size
        compression_percent = (1 - compression_ratio) * 100
        
        console.log(f"Compressed file size: {compressed_size:,.0f} kb")
        console.log(f"Compression ratio: {compression_ratio:.2%}")
        
        # Prepare file for download - each file gets its own unique download ID
        download_id = prepare_file_for_download(compressed_filename)
        
        # Add to results table with download button
        table = get_element("tbody")
        download_data = processed_files[download_id]
        
        # Use consistent is-info tag for all compression information
        tag_class = "is-info"
        
        # Check if this preset already exists in the table
        existing_row = None
        for row in document.querySelectorAll("tbody tr"):
            if row.querySelector("td:first-child span") and row.querySelector("td:first-child span").textContent == compressed_filename:
                existing_row = row
                break
                
        if existing_row:
            # Update the existing row
            existing_row.innerHTML = f"""
                <td>
                    <span>{compressed_filename}</span>
                    <span class="tag {tag_class} is-light ml-2">{preset_display_name}</span>
                </td>
                <td>
                    <span>{compressed_size:,.0f} kb</span>
                    <span class="tag {tag_class} is-light ml-2">{compression_percent:.1f}% smaller</span>
                </td>
                <td>
                    <button class="button is-info" onclick="window.sovPdfDownload('{download_data['data']}', '{download_data['filename']}')">
                        <span class="icon is-small">
                            <i class="fa fa-download"></i>
                        </span>
                        <span>Save</span>
                    </button>
                </td>
            """
        else:
            # Add a new row
            table.innerHTML += f"""<tr>
                                <td>
                                    <span>{compressed_filename}</span>
                                    <span class="tag {tag_class} is-light ml-2">{preset_display_name}</span>
                                </td>
                                <td>
                                    <span>{compressed_size:,.0f} kb</span>
                                    <span class="tag {tag_class} is-light ml-2">{compression_percent:.1f}% smaller</span>
                                </td>
                                <td>
                                    <button class="button is-info" onclick="window.sovPdfDownload('{download_data['data']}', '{download_data['filename']}')">
                                        <span class="icon is-small">
                                            <i class="fa fa-download"></i>
                                        </span>
                                        <span>Save</span>
                                    </button>
                                </td>
                            </tr>"""
        
        console.log("UI updated with result")
        
        # Show the clear button when we have results in the table
        get_element("#clearButton").classList.remove("is-hidden")
        
        # Show success notification with display name
        show_notification(f"PDF compressed successfully with {preset_display_name} preset! Saved {compression_percent:.1f}% of space", "is-info")
        
        # Reset button loading state
        set_button_loading(button_id, False)
        
        is_processing = False
        current_button = None
        return True
    except Exception as e:
        handle_error(f"Error processing PDF: {str(e)}")
        return False

# Centralized error handling
def handle_error(error_message):
    """Centralized function for handling errors"""
    console.error(error_message)
    # Show error notification
    show_notification(error_message, "is-danger")
    # Reset button loading state if there's an active button
    global current_button, is_processing
    if current_button:
        set_button_loading(current_button, False)
        current_button = None
    # Set processing flag to false to allow new operations
    is_processing = False

# Function to show notifications
def show_notification(message, type="is-info"):
    """Display a notification message to the user
    
    Parameters:
        message: str - The message to display
        type: str - The Bulma notification type (is-info, is-success, is-warning, is-danger)
    """
    try:
        # Get the notification element
        notification = get_element("#notification")
        
        # Update the notification content
        notification.className = f"notification {type} is-light"
        notification.innerHTML = f"""
            <button class="delete" onclick="this.parentElement.classList.add('is-hidden')"></button>
            {message}
        """
        
        # Show the notification
        notification.classList.remove("is-hidden")
        
        # Set a timeout to hide the notification after 5 seconds
        # Using direct JS approach instead of eval
        js_code = """
        setTimeout(function() {
            document.querySelector('#notification').classList.add('is-hidden');
        }, 5000);
        """
        
        # Execute the timeout code directly
        script = document.createElement('script')
        script.textContent = js_code
        document.head.appendChild(script)
        
    except Exception as e:
        # Log error but don't try to show another notification (to avoid infinite loop)
        console.error(f"Error showing notification: {str(e)}")

# Generic event handler for preset buttons
@when("click", ".button[id$='Button']")
async def preset_button_handler(event):
    button_id = event.target.id
    if not button_id or not button_id.endswith('Button'):
        # If click happened on a child element, find the parent button
        parent = event.target.closest('.button[id$="Button"]')
        if parent:
            button_id = parent.id
        else:
            return
            
    preset = button_id.replace('Button', '').lower()
    
    # Skip handling for the clearButton
    if button_id == "clearButton":
        return
        
    if preset not in ['medium', 'small', 'tiny']:  # Changed from 'normal' to 'medium'
        console.error(f"Unknown preset: {preset}")
        return
        
    global selected_preset
    selected_preset = preset
    console.log(f"{preset.capitalize()} preset selected")
    highlight_selected_button(button_id)
    
    # Process the PDF if we have one loaded
    if current_pdf:
        await process_pdf(current_pdf, preset)

@when("change", "#filePdf")
async def file_change_handler(event):
    """Handle file selection from the file input"""
    try:
        input = event.target
        
        # Check if files were actually selected
        if not input.files or input.files.length == 0:
            console.log("No files selected")
            return
        
        # We only process the first file, even if multiple were somehow selected
        file = input.files.item(0)
        
        # Load the PDF file using the shared helper function
        await load_pdf_file(file)
        
    except Exception as e:
        console.error(f"Error in file selection handler: {str(e)}")
        show_notification(f"Error loading PDF: {str(e)}", "is-danger")

# Function to reset the application state
def reset_app():
    """Reset the application to a clean state"""
    global current_pdf, current_pdf_size, processed_files
    
    # Clean up temporary files
    cleanup_files()
    
    # Clear the results table
    tbody = get_element("tbody")
    if tbody:
        tbody.innerHTML = ""
    
    # Clear processed files dictionary
    processed_files.clear()
    
    # Reset the file input - we need to use a trick to reset the file input
    file_input = get_element("#filePdf")
    if file_input:
        file_input.value = ""
    
    # Hide the clear button
    clear_btn = get_element("#clearButton")
    if clear_btn:
        clear_btn.classList.add("is-hidden")
    
    # Reset current PDF references
    current_pdf = None
    current_pdf_size = 0
    
    show_notification("Application reset to clean state", "is-info")

# Event handler for clear button
@when("click", "#clearButton")
def clear_button_handler(event):
    """Handle clear button click to reset application state"""
    console.log("Clear button clicked, resetting app state")
    reset_app()

# Initialize the application
def main():
    # Highlight the default preset button
    highlight_selected_button("mediumButton")  # Changed from normalButton to mediumButton
    
    # Setup drag and drop functionality
    setup_drag_and_drop()
    
    # Setup page unload handler for cleanup using direct JavaScript
    js_code = """
    window.addEventListener('beforeunload', function() {
        // This will trigger Python's cleanup via a custom event
        document.dispatchEvent(new CustomEvent('py-cleanup'));
    });
    """
    script = document.createElement('script')
    script.textContent = js_code
    document.head.appendChild(script)
    
    # Listen for the custom cleanup event
    document.addEventListener('py-cleanup', cleanup_files)
    
    console.log("App initialized")

# Setup drag and drop functionality
def setup_drag_and_drop():
    """Set up event listeners for drag and drop functionality"""
    drop_zone = get_element("#dropZone")
    
    if not drop_zone:
        console.error("Drop zone element not found")
        return
    
    # JavaScript code to ensure drag and drop works properly with hover highlighting
    js_code = """
    // Prevent default behavior for the document to avoid browser opening files
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      document.addEventListener(eventName, function(e) {
        if (!e.target.closest('#dropZone')) {
          e.preventDefault();
          e.stopPropagation();
        }
      }, false);
    });

    // Handle the drop zone specific events
    const dropZone = document.getElementById('dropZone');
    
    // Highlight the drop zone on dragenter/dragover
    dropZone.addEventListener('dragenter', function(e) {
      e.preventDefault();
      this.classList.add('is-info');
    }, false);
    
    dropZone.addEventListener('dragover', function(e) {
      e.preventDefault();
      this.classList.add('is-info');
    }, false);
    
    // Remove highlight on dragleave/drop
    dropZone.addEventListener('dragleave', function(e) {
      e.preventDefault();
      this.classList.remove('is-info');
    }, false);
    
    // Handle the drop event in JavaScript
    dropZone.addEventListener('drop', function(e) {
      e.preventDefault();
      e.stopPropagation();
      this.classList.remove('is-info');
      
      const dt = e.dataTransfer;
      if (dt.files && dt.files.length > 0) {
        const file = dt.files[0];
        
        // Check if it's a PDF
        if (!file.name.toLowerCase().endsWith('.pdf')) {
          console.error('Not a PDF file');
          // Show alert - we can't call Python functions directly from here
          alert('Please drop a PDF file');
          return;
        }
        
        console.log('JavaScript: PDF file dropped, processing directly');
        
        // Create a new FileList containing this file
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        
        // Set the file to the input element
        const fileInput = document.getElementById('filePdf');
        fileInput.files = dataTransfer.files;
        
        // Trigger change event on the file input element
        // Note: We need to create a new Event with the 'new' keyword
        fileInput.dispatchEvent(new Event('change'));
      }
    }, false);
    """
    
    # Execute the JavaScript directly for better browser compatibility
    script = document.createElement('script')
    script.textContent = js_code
    document.head.appendChild(script)
    
    console.log("Drag and drop functionality set up")

# Process a dropped file directly (used as fallback)
async def process_dropped_file(file):
    """Process a dropped file directly if setting the file input fails"""
    console.log("Using fallback file processing method")
    await load_pdf_file(file)

async def load_pdf_file(file):
    """
    Process a PDF file - common functionality for both file input and drag-drop
    
    Args:
        file: JavaScript File object
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        global current_pdf, current_pdf_size
        
        # Clean up any existing files
        cleanup_files()
        
        # Get file name
        pdf = file.name
        console.log(f"Loading file: {pdf}")
        
        # Validate file type
        if not pdf.lower().endswith('.pdf'):
            console.error("Not a PDF file")
            show_notification("Please select a PDF file", "is-warning")
            return False
            
        # Create a temporary URL
        tmp = window.URL.createObjectURL(file)
        console.log("URL created")
        
        # Fetch and save its content
        console.log("Fetching file content...")
        with open(pdf, "wb") as dest:
            dest.write(await fetch(tmp).bytearray())
        console.log("File saved locally")
        
        # Track this file for cleanup
        temp_files.append(pdf)
        
        # Revoke the tmp URL
        window.URL.revokeObjectURL(tmp)
        
        # Store current PDF filename and size
        current_pdf = pdf
        current_pdf_size = os.path.getsize(pdf) / 1024
        
        # Clear the results table
        get_element("tbody").innerHTML = ""
        
        # Clear processed files dictionary
        processed_files.clear()
        
        # Add the original PDF to the results table with a distinctive style
        table = get_element("tbody")
        
        # Add original file as first row with a neutral style - using is-light
        table.innerHTML = f"""<tr class="is-selected has-background-light">
                            <td>
                                <span class="has-text-weight-bold">{pdf}</span>
                                <span class="tag is-info is-light ml-2">Original</span>
                            </td>
                            <td>
                                <span>{current_pdf_size:,.0f} kb</span>
                            </td>
                            <td>
                                <span class="has-text-grey-light">Selected file</span>
                            </td>
                        </tr>"""
    
        # Show the clear button since we have a file loaded
        get_element("#clearButton").classList.remove("is-hidden")
        
        console.log(f"Original file size: {current_pdf_size:,.0f} kb")
        
        return True
        
    except Exception as e:
        console.error(f"Error loading PDF: {str(e)}")
        # Show error notification
        show_notification(f"Error loading PDF: {str(e)}", "is-danger")
        return False

# Call main after all functions are defined
main()

