import os
import re
import json
import requests
import ebooklib
import gradio as gr

from ebooklib import epub
from bs4 import BeautifulSoup

class Book:
    def __init__(self, file_path):
        self.file_path = file_path
        self.title = None
        self.cover = None
        self.chapters = {}
        self.images = []

        self._load_book()

    def _load_book(self):
        book = epub.read_epub(self.file_path)
        self.title = book.get_metadata('DC', 'title')[0][0] if book.get_metadata('DC', 'title') else 'Unknown Title'

        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                self._process_chapter(item.content)
            elif item.get_type() == ebooklib.ITEM_IMAGE:
                self.images.append(item.get_content())
            elif item.get_type() == ebooklib.ITEM_COVER:
                self.cover = item.get_content()

    def _process_chapter(self, content):
        soup = BeautifulSoup(content, 'html.parser')
        for tag in soup.find_all(['h1']):
            chapter_name = tag.get_text().strip() if tag else "Unnamed Chapter"
            chapter_text = soup.get_text().strip()
            self.chapters[chapter_name] = chapter_text

    def check_chapters_content(self):
        for chapter_name, chapter_text in self.chapters.items():
            if not chapter_text.strip():
                return False, chapter_name
        return True, None

def initialize_books_from_directory(directory):
    books = []
    for filename in os.listdir(directory):
        if filename.endswith('.epub'):
            file_path = os.path.join(directory, filename)
            books.append(Book(file_path))
    return books

# Loop through each book and print its title
def get_book_titles():
    titles = []
    for book in books:
        titles.append(book.title)
    return titles

def split_into_sentences(text):
    # Simple sentence splitter using regex
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s', text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]

def save_current_state(book_reader, file_path='current_state.json'):
    state = {
        'current_book': book_reader.current_book,
        'current_chapter_index': book_reader.current_chapter_index,
        'current_sentence_index': book_reader.current_sentence_index
    }
    with open(file_path, 'w') as file:
        json.dump(state, file)

def load_saved_state(book_reader, file_path='current_state.json'):
    try:
        with open(file_path, 'r') as file:
            state = json.load(file)
            book_reader.set_current_book(state['current_book'])
            book_reader.current_chapter_index = state['current_chapter_index']
            book_reader.current_sentence_index = state['current_sentence_index']
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        # Handle the case where the state file doesn't exist or is invalid
        print("No saved state found or state is invalid. Starting from the beginning.")

class BookReader:
    def __init__(self, books):
        self.books = {book.title: book for book in books}
        self.current_book = None
        self.current_chapter_index = 0
        self.current_sentence_index = 0
        self.sentences = []
        self.previous_chapter_text = None

    def set_current_book(self, title):
        self.current_book = title
        self.current_chapter_index = 0
        self.current_sentence_index = 0
        self.sentences = []

    def load_chapter(self, title):
        if title not in self.books:
            return "Book not found."

        if self.current_book != title:
            self.current_book = title
            self.current_chapter_index = -1

        book = self.books[title]
        self.current_chapter_index += 1

        chapters = list(book.chapters.keys())
        if self.current_chapter_index < len(chapters):
            return book.chapters[chapters[self.current_chapter_index]]
        else:
            return "No more chapters available."
        
    def load_next_sentence(self):
        if self.current_book is None:
            return "No book selected"

        book = self.books[self.current_book]
        chapters = list(book.chapters.values())

        if self.current_sentence_index >= len(self.sentences):
            while self.current_chapter_index < len(chapters):
                current_chapter_text = chapters[self.current_chapter_index]
                
                if self.has_chapter_text_changed(current_chapter_text):
                    self.sentences = split_into_sentences(current_chapter_text)
                    self.current_sentence_index = 0
                    self.previous_chapter_text = current_chapter_text
                    break
                else:
                    self.current_chapter_index += 1
            else:
                return "End of the book"

        current_sentence = self.sentences[self.current_sentence_index]
        highlighted_text = chapters[self.current_chapter_index].replace(current_sentence, f"<span style='color: red;'>{current_sentence}</span>")
        self.current_sentence_index += 1
        return highlighted_text

    def get_current_chapter_text(self):
        if self.current_book is None or self.current_chapter_index >= len(self.books[self.current_book].chapters):
            return ""
        book = self.books[self.current_book]
        chapters = list(book.chapters.values())
        return chapters[self.current_chapter_index - 1]
    
    def get_chapter_with_highlighted_sentence(self):
        if self.current_book is None:
            return "No book selected"

        book = self.books[self.current_book]
        chapter_text = self.get_current_chapter_text()
        sentences = split_into_sentences(chapter_text)

        if self.current_sentence_index < len(sentences):
            highlighted_sentence = sentences[self.current_sentence_index]
            highlighted_text = chapter_text.replace(highlighted_sentence, f"<span style='color: red;'>{highlighted_sentence}</span>")
            return highlighted_text
        else:
            return chapter_text

    def get_current_sentence(self):
        if self.current_book and self.sentences:
            return self.sentences[self.current_sentence_index]
        return ""
        
    def repeat_current_sentence(self):
        if self.current_book is None or not self.sentences:
            return "No book selected or no current sentence."

        book = self.books[self.current_book]
        chapters = list(book.chapters.values())

        if self.current_chapter_index < len(chapters):
            chapter_text = chapters[self.current_chapter_index]

            index_for_repeat = self.current_sentence_index - 1 if self.current_sentence_index > 0 else 0
            current_sentence = self.sentences[index_for_repeat]

            highlighted_text = chapter_text.replace(current_sentence, f"<span style='color: red;'>{current_sentence}</span>")
            return highlighted_text
        else:
            return "Chapter index out of range"

    def previous_sentence(self):
        if self.current_book is None:
            return "No book selected"

        if self.current_sentence_index == 0:
            if self.current_chapter_index > 0:
                self.current_chapter_index -= 1
                previous_chapter_text = self.books[self.current_book].chapters[list(self.books[self.current_book].chapters)[self.current_chapter_index]]
                self.sentences = split_into_sentences(previous_chapter_text)
                self.current_sentence_index = len(self.sentences) - 1
            else:
                return "Already at the beginning of the book"
        else:
            self.current_sentence_index -= 1

        current_sentence = self.sentences[self.current_sentence_index]
        chapter_text = self.books[self.current_book].chapters[list(self.books[self.current_book].chapters)[self.current_chapter_index]]
        highlighted_text = chapter_text.replace(current_sentence, f"<span style='color: red;'>{current_sentence}</span>")
        return highlighted_text
    
    def has_chapter_text_changed(self, current_chapter_text):
        if self.previous_chapter_text is None:
            return True  # No previous chapter, so text has "changed"
        return self.previous_chapter_text != current_chapter_text

# Initialize books and BookReader
books = initialize_books_from_directory('Books')
book_reader = BookReader(books)
load_saved_state(book_reader)

def update_chapter(title):
    return book_reader.load_chapter(title)

def go_to_saved_point():
    load_saved_state(book_reader)
    if book_reader.current_book:
        book_reader.sentences = split_into_sentences(book_reader.get_current_chapter_text())
        return book_reader.current_book, book_reader.get_chapter_with_highlighted_sentence()
    return "", "No saved point or book not found."

def get_audio_from_api(sentence):
    api_url = "https://your-api-endpoint.com/generate_audio"
    response = requests.post(api_url, json={"sentence": sentence})
    
    if response.status_code == 200:
        # Assuming the API returns the audio file directly
        return response.content
    else:
        return None

javascript = """
function autoPlayAudio() {
    var audioElements = document.getElementsByTagName('audio');
    if (audioElements.length > 0) {
        var audioElement = audioElements[0];
        audioElement.onloadeddata = function() {
            audioElement.play();
        };
    }
}
"""

with gr.Blocks(theme=gr.themes.Monochrome()) as demo:
    with gr.Tab("Book-2-Audio"):
        book_select = gr.Dropdown(get_book_titles(), label="Choose Book")
        audio_player = gr.Audio(label="Audio Playback", elem_id="audio_elem")
        chapter_display = gr.HTML(label="Chapter Text")
        with gr.Row():
            next_sentence = gr.Button('Next Sentence')
            repeat_sentence = gr.Button('Repeat Sentence')
            prev_sentence = gr.Button('Previous Sentence')
        go_to_saved_button = gr.Button('Go to Saved Point')

    def update_book_selection(title):
        book_reader.set_current_book(title)
        book_reader.current_chapter_index = 0
        book_reader.current_sentence_index = 0
        return book_reader.load_next_sentence()

    def update_sentence():
        highlighted_text = book_reader.load_next_sentence()
        save_current_state(book_reader)
        return highlighted_text
    
    def get_TTS():
        sentence = book_reader.get_current_sentence()
        audio_content = get_audio_from_api(sentence)
        if audio_content:
            with open("temp_audio.mp3", "wb") as file:
                file.write(audio_content)
            gr.update(js="autoPlayAudio()")
            return "temp_audio.mp3"
        else:
            return None

    book_select.change(update_book_selection, inputs=[book_select], outputs=[chapter_display])
    next_sentence.click(update_sentence, inputs=[], outputs=[chapter_display])
    next_sentence.click(get_TTS, inputs=[], outputs=[audio_player])
    repeat_sentence.click(lambda: book_reader.repeat_current_sentence(), inputs=[], outputs=[chapter_display])
    prev_sentence.click(lambda: book_reader.previous_sentence(), inputs=[], outputs=[chapter_display])
    go_to_saved_button.click(go_to_saved_point, inputs=[], outputs=[book_select, chapter_display])

demo.queue()
demo.launch()
