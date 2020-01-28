'''
This is the Orange Media Server video encoder.
This encoder is only to be invoked by the daemon process running on the database. This is to ensure
any shell access is kept to a minimum, boosting security.

It is a simple ffmpeg wrapper with a bunch of presets compatible with video files. It also manages the 
data structure of videos.
'''
import subprocess
import os
import time


class VideoEncoder():
    def __init__(self):
        self.FFMPEG = 'ffmpeg' if os.name != 'nt' else 'C:/Users/danie/Desktop/ffmpeg.exe'
        self.FFPROBE = 'ffprobe' if os.name != 'nt' else 'C:/Users/danie/Desktop/ffprobe.exe'
        self.PRESETS = {
            'x264': self.FFMPEG+' -i {:s} -c:v x264_nvenc -c:a aac {:s}',
            'hls': self.FFMPEG+' -i {:s} -c:v copy -c:a copy -f segment -segment_list {:s}.m3u8 -segment_list_flags +live -segment_time 5 {:s}%03d.ts',
            'aac': self.FFMPEG+' -i {:s} -c:v copy -c:a aac {:s}',
            'vid_probe': self.FFPROBE+' -v error -select_streams v:0 -show_entries stream=width,height,duration,bit_rate,codec_name -of default=noprint_wrappers=1 {:s}',
            'aud_probe': self.FFPROBE+' -v error -select_streams a:0 -show_entries stream=bit_rate,codec_name -of default=noprint_wrappers=1 {:s}'
        }
        self.preset = False
        self.temp_dir = False

    def valid_preset(self, preset):
        '''
        determines if the preset is a valid preset
        '''
        return preset in list(self.PRESETS)

    def set_temporary_directory(self, new_dir):
        '''
        Sets the temp directory
        '''
        self.temp_dir = new_dir

    def _format_probe_output(self, process):
        '''
        Formats the STDOUT byte package to a dict
        '''
        formatted_output = {}
        proc_output = process.stdout.decode("utf-8").split('\n')
        for k in proc_output:
            if k == "":
                continue
            val = k.split('=')
            formatted_output[val[0].rstrip()] = val[1].rstrip()
        return formatted_output

    def _probe(self, path):
        '''
        Determines the video and audio codec metadata
        '''
        vid_proc = subprocess.run(self.PRESETS['vid_probe'].format(
            path), shell=True, capture_output=True)

        aud_proc = subprocess.run(self.PRESETS['aud_probe'].format(
            path), shell=True, capture_output=True)

        probe = {
            "video": self._format_probe_output(vid_proc),
            "audio": self._format_probe_output(aud_proc)
        }

        return probe

    def _encode_hls(self, output_path, name, path):
        '''
        Takes an output_path directory and outputs the path file in the hls format, with the manifest name and part name being name
        '''
        full_path = output_path+'/'+name
        start_time = time.time()
        process = subprocess.run(
            self.PRESETS['hls'].format(path, full_path, full_path), shell=True, capture_output=True)

        if(process.stderr):
            print(process.stderr.decode('utf-8'))
            return False
        else:
            exec_time = (time.time()) - start_time
            return(exec_time)

    def _encode_aac(self, output_path, name, path):
        '''
        encodes the file and gives the output a temporary file name
        '''

        process = subprocess.run(self.PRESETS['aac'].format(
            path, output_path+'/'+name+'_aac.mp4'))
        if(process.stderr):
            print(process.stderr.decode('utf-8'))
        return(output_path+'/'+name+'_aac.mp4')

    def _encode_x264(self, output_path, name, path):
        '''
        Envokes nvidias NVENC encoder preset for ffmpeg to use a graphics card to help speed up the encoding process
        Since my gpu sucks this will be a slow process
        '''
        process = subprocess.run(self.PRESETS['x264'].format(
            path, output_path+"/"+name+"_x264.mp4"))
        if(process.stderr):
            print(process.stderr.decode('utf-8'))
        return(output_path+"/"+name+'_x264.mp4')

    def auto_encode(self, path, name, output_path):
        '''
        Selects the best preset to use.
        name - Name of the video file and the manifest file
        path - The path to the input file
        output_path - The path to the output directory (the temporary file directory will be used if previously set)
        '''
        if(os.path.isfile(path)):
            if(not os.path.exists(output_path)):
                os.mkdir(output_path)
            probe = self._probe(path)
            if(probe['video']['codec_name'] == 'h264' and probe['audio']['codec_name'] == 'aac'):
                # Only HLS encoding is necessary
                stream_execution_time = self._encode_hls(
                    output_path, name, path)
                return stream_execution_time

            if(probe['audio']['codec_name'] == 'h264' and probe['audio']['codec_name'] != 'aac'):
                # encode to aac and then to HLS
                intermediate_path = self._encode_aac(
                    output_path, name, path)
                stream_execution_time = self._encode_hls(
                    output_path, name, intermediate_path)
                # delete the temporary file
                os.remove(intermediate_path)
                return stream_execution_time
            else:
                # anything else needs to be encoded into the h264 format
                # this is the most compute-intensive part of the process and
                # should really be offloaded to a gpu instance or something.
                intermediate_path = self._encode_x264(output_path, name, path)
                exec_time = self._encode_hls(
                    output_path, name, intermediate_path)

                return exec_time

        else:
            return False
