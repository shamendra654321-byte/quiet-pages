import queue, threading, unittest
import numpy as np
from chapter_audio import read_book

class DecorativeSpeechTests(unittest.TestCase):
    def play(self,parts,engine,start=0):
        spoken=[]
        class Stream:
            def __init__(self,**kwargs): pass
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def write(self,data): spoken.extend(data[:,0])
        events=queue.Queue(); errors=[]
        def run():
            try: read_book(engine,parts,start,len(parts),list(range(len(parts))),'af_heart',1,threading.Event(),threading.Event(),events,Stream,buffer_seconds=10)
            except Exception as e: errors.append(e)
        worker=threading.Thread(target=run,daemon=True);worker.start();worker.join(4)
        self.assertFalse(worker.is_alive(),'Skipped chapters must not deadlock lookahead')
        if errors: raise errors[0]
        return spoken,events
    def test_separators_across_whole_chapters_continue_and_resume(self):
        calls=[]
        class Engine:
            def create(self,text,**kwargs): calls.append(text);return np.ones(100),24000
        parts=['First words','✦ ✦ ✦','***','—','Next words','...']
        spoken,events=self.play(parts,Engine())
        self.assertEqual(calls,['First words','Next words']);self.assertEqual(len(spoken),200)
        calls.clear();self.play(parts,Engine(),start=1);self.assertEqual(calls,['Next words'])
    def test_only_specific_no_phonemes_error_is_skipped(self):
        class Engine:
            def create(self,text,**kwargs):
                if text=='unsupported':raise ValueError("Nothing to synthesize, 'unsupported' produced no phonemes")
                return np.ones(50),24000
        samples,_=self.play(['unsupported','Story continues'],Engine());self.assertEqual(len(samples),50)
        class Broken:
            def create(self,text,**kwargs):raise ValueError('model failed')
        with self.assertRaisesRegex(ValueError,'model failed'):self.play(['Story'],Broken())
    def test_all_symbols_never_load_engine_or_open_audio(self):
        def engine():self.fail('Decorative text should not load voice engine')
        samples,_=self.play(['✦','---','***','…'],engine);self.assertEqual(samples,[])
