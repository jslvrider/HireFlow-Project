import uuid
from pathlib import Path
import shutil



def create_folder(doc_id: str) -> Path:
    folder_path = Path("resume_uploads") / doc_id
    folder_path.mkdir(parents=True)
    return folder_path

def copy_file(source_path: str, destination_path: str) ->None:
    shutil.copy(source_path, destination_path)
    


def upload_file(pdf_path: str, username: str) -> tuple[str, str, str]:
        
    doc_id = str(uuid.uuid4())

    folder_path = create_folder(doc_id = doc_id)

    pdf_filename = Path(pdf_path).name

    source_path = pdf_path 
    
    destination_path = folder_path / pdf_filename

    copy_file(source_path=source_path, destination_path=destination_path)

    file_link = str(destination_path)
    
    return doc_id, file_link, username 
