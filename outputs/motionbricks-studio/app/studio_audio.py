"""Windows native MP3/WAV transport, with decoder time as the playback clock."""
import ctypes
from pathlib import Path
import uuid
import tempfile
import wave
import shutil


class AudioTransport:
    def __init__(self):
        self.path=None
        self.alias='studio_'+uuid.uuid4().hex
        self.duration=0.
        self._decoded=None
        self._api=ctypes.WinDLL('winmm')
        self._api.mciSendStringW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_void_p]

    def command(self,value):
        result=ctypes.create_unicode_buffer(1024)
        error=self._api.mciSendStringW(value,result,len(result),None)
        if error:
            self._api.mciGetErrorStringW(error,result,len(result))
            raise RuntimeError(result.value)
        return result.value

    def load(self,path):
        path=Path(path).resolve()
        if path.suffix.lower() not in ('.mp3','.wav') or not path.is_file():
            raise ValueError('Choose an existing MP3 or WAV file.')
        # Validate the replacement before closing the existing track.
        alias='studio_'+uuid.uuid4().hex
        decoded=None
        try:
            # Legacy MCI drivers can reject long paths even with the Unicode API.
            decoded=tempfile.TemporaryDirectory(prefix='studio_audio_')
            playback_path=Path(decoded.name)/'audio.wav'
            if path.suffix.lower()=='.mp3':
                # Legacy Windows MP3 drivers misreport VBR duration and seek positions.
                # Decode to PCM first so both formats use the same precise timeline.
                import miniaudio
                audio=miniaudio.decode(path.read_bytes(),output_format=miniaudio.SampleFormat.SIGNED16,
                                           nchannels=2,sample_rate=44100)
                with wave.open(str(playback_path),'wb') as wav:
                    wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(44100)
                    wav.writeframes(audio.samples.tobytes())
            else:shutil.copyfile(path,playback_path)
            self.command(f'open "{playback_path}" alias {alias}')
            self.command(f'set {alias} time format milliseconds')
            duration=float(self.command(f'status {alias} length'))/1000
        except Exception:
            try:self.command(f'close {alias}')
            except Exception:pass
            if decoded:decoded.cleanup()
            raise
        self.close()
        self.alias,self.path,self.duration=alias,path,duration
        self._decoded=decoded

    @property
    def position(self):
        return float(self.command(f'status {self.alias} position'))/1000 if self.path else 0.

    @property
    def playing(self):
        return self.command(f'status {self.alias} mode')=='playing' if self.path else False

    def play(self):
        if self.path:
            if self.position>=self.duration-.01:self.seek(0)
            self.command(f'play {self.alias}')

    def pause(self):
        if self.path and self.playing:self.command(f'pause {self.alias}')

    def seek(self,seconds):
        if self.path:
            playing=self.playing
            milliseconds=min(round(self.duration*1000),max(0,round(seconds*1000)))
            self.command(f'seek {self.alias} to {milliseconds}')
            if playing and milliseconds<round(self.duration*1000):self.command(f'play {self.alias}')

    def close(self):
        if self.path:
            self.command(f'close {self.alias}')
            self.path=None;self.duration=0.
            if self._decoded:self._decoded.cleanup();self._decoded=None

# MotionBricks Studio Ti distribution: customized by MASATAKA; see NOTICE.md.
