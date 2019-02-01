# -*- coding: utf-8 -*-
# /usr/bin/python2
'''
By kyubyong park. kbpark.linguist@gmail.com.
https://www.github.com/kyubyong/dc_tts
'''

from __future__ import print_function

import os

import numpy as np
import tensorflow as tf
# from graphs import Graph
from architectures import Text2MelGraph, SSRNGraph, BabblerGraph

from utils import *
from data_load import load_data
from scipy.io.wavfile import write
from tqdm import tqdm

## to import configs
# HERE = os.path.realpath(os.path.abspath(os.path.dirname(__file__)))
# sys.path.append( HERE + '/config/' )
# import importlib
import imp

from libutil import safe_makedir, basename, load_config

from argparse import ArgumentParser


import timeit 

def start_clock(comment):
    print ('%s... '%(comment)),
    return (timeit.default_timer(), comment)

def stop_clock((start_time, comment), width=40):
    padding = (width - len(comment)) * ' '
    print ('%s--> took %.2f seconds' % (padding, (timeit.default_timer() - start_time)) )

def denorm(data, stats, type):
    if type=='minmax':
        mini = stats[0,:].reshape(1,-1)
        maxi = stats[1,:].reshape(1,-1)  
        X = data   
        # http://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.MinMaxScaler.html
        X_std = (X - X.min(axis=0)) / (X.max(axis=0) - X.min(axis=0))
        X_scaled = X_std * (maxi - mini) + mini   
        return X_scaled        
    elif type=='meanvar':
        mean = stats[0,:].reshape(1,-1)
        std = stats[1,:].reshape(1,-1)
        data = (data * std) + mean
    else:
        sys.exit('Unknown normtype: %s'%(type))
    return data

# import re
# def basename(fname):
#     path, name = os.path.split(fname)
#     base = re.sub('\.[^\.]+\Z','',name)
#     return base

### TODO: refactor, replace loop in synthesize function with this
def synth_text2mel(hp, L, g, sess, speaker_data=None):
    '''
    L: texts
    g: synthesis graph
    sess: Session
    '''
    Y = np.zeros((len(L), hp.max_T, hp.n_mels), np.float32)
    prev_max_attentions = np.zeros((len(L),), np.int32)

    # if speaker_codes:

    #     speaker_data = np.zeros_like(L)
    #     for i in range(len(L)):
    #         speaker_ix = 
    #         length = (np.where(L[i,:]==0)[0][0])
    #         speaker_data[i,:length] = speaker_ix


    ### -- set up counters to detect & record sentence end, used for trimming and early stopping --
    ends = []  ## indices of first padding character after the last letter
    for i in range(len(L)):
        ends.append((np.where(L[i,:]==0)[0][0]))
    ends = np.array(ends)
    endcounts = np.zeros(ends.shape, dtype=int)  ## counts of the number of times attention has focussed (max) on these indices
    endcount_threshold = 1 ## number of times we require attention to focus on end before we consider synthesis finished
    t_ends = np.ones(ends.shape, dtype=int) * hp.max_T  ## The frame index when endcounts is sufficiently high, which we'll consider the end of the utterance
                                                        ## NB: initialised to max_T -- will default to this.

    t = start_clock('gen')
    for j in tqdm(range(hp.max_T)):
        if hp.multispeaker:
            _Y, _max_attentions, _alignments, = \
                sess.run([ g.Y, g.max_attentions, g.alignments],
                         {g.L: L,
                          g.mels: Y,
                          g.speakers: speaker_data,
                          g.prev_max_attentions: prev_max_attentions}) ##
        else:
            _Y, _max_attentions, _alignments, = \
                sess.run([ g.Y, g.max_attentions, g.alignments],
                         {g.L: L,
                          g.mels: Y,
                          g.prev_max_attentions: prev_max_attentions}) ## osw: removed global_step from synth loop
        Y[:, j, :] = _Y[:, j, :]
        prev_max_attentions = _max_attentions[:, j]

        ## Work out if we've reach end of any/all sentences in batch:-
        reached_end = (_max_attentions[:, j] >= ends) ## is attention focussing on or beyond end of textual sentence?
        endcounts += reached_end
        for (i,(current, endcount)) in enumerate(zip(t_ends, endcounts)):
            if current == hp.max_T: ## if hasn't changed from initialisation value
                if endcount >= endcount_threshold:
                    t_ends[i] = j
        ## Bail out early if all sentences seem to be finished:
        if (t_ends < hp.max_T).all():
            print('finished here:')
            print(t_ends)
            break

    return (Y, t_ends.tolist())


## TODO: compare efficiency  etc with encode_text + synth_codedtext2mel and possibly remove this version
def synth_text2mel(hp, L, g, sess, speaker_data=None):
    '''
    L: texts
    g: synthesis graph
    sess: Session
    '''
    Y = np.zeros((len(L), hp.max_T, hp.n_mels), np.float32)
    prev_max_attentions = np.zeros((len(L),), np.int32)

    # if speaker_codes:

    #     speaker_data = np.zeros_like(L)
    #     for i in range(len(L)):
    #         speaker_ix = 
    #         length = (np.where(L[i,:]==0)[0][0])
    #         speaker_data[i,:length] = speaker_ix


    ### -- set up counters to detect & record sentence end, used for trimming and early stopping --
    ends = []  ## indices of first padding character after the last letter
    for i in range(len(L)):
        ends.append((np.where(L[i,:]==0)[0][0]))
    ends = np.array(ends)
    endcounts = np.zeros(ends.shape, dtype=int)  ## counts of the number of times attention has focussed (max) on these indices
    endcount_threshold = 1 ## number of times we require attention to focus on end before we consider synthesis finished
    t_ends = np.ones(ends.shape, dtype=int) * hp.max_T  ## The frame index when endcounts is sufficiently high, which we'll consider the end of the utterance
                                                        ## NB: initialised to max_T -- will default to this.

    t = start_clock('gen')
    for j in tqdm(range(hp.max_T)):
        if hp.multispeaker:
            _Y, _max_attentions, _alignments, = \
                sess.run([ g.Y, g.max_attentions, g.alignments],
                         {g.L: L,
                          g.mels: Y,
                          g.speakers: speaker_data,
                          g.prev_max_attentions: prev_max_attentions}) ##
        else:
            _Y, _max_attentions, _alignments, = \
                sess.run([ g.Y, g.max_attentions, g.alignments],
                         {g.L: L,
                          g.mels: Y,
                          g.prev_max_attentions: prev_max_attentions}) ## osw: removed global_step from synth loop
        Y[:, j, :] = _Y[:, j, :]
        prev_max_attentions = _max_attentions[:, j]

        ## Work out if we've reach end of any/all sentences in batch:-
        reached_end = (_max_attentions[:, j] >= ends) ## is attention focussing on or beyond end of textual sentence?
        endcounts += reached_end
        for (i,(current, endcount)) in enumerate(zip(t_ends, endcounts)):
            if current == hp.max_T: ## if hasn't changed from initialisation value
                if endcount >= endcount_threshold:
                    t_ends[i] = j
        ## Bail out early if all sentences seem to be finished:
        if (t_ends < hp.max_T).all():
            print('finished here:')
            print(t_ends)
            break

    return (Y, t_ends.tolist())



def synth_codedtext2mel(hp, K, V, ends, g, sess, speaker_data=None):
    '''
    K, V: coded texts
    g: synthesis graph
    sess: Session
    '''
    Y = np.zeros((len(K), hp.max_T, hp.n_mels), np.float32)
    prev_max_attentions = np.zeros((len(K),), np.int32)

    ### -- set up counters to detect & record sentence end, used for trimming and early stopping --

    endcounts = np.zeros(ends.shape, dtype=int)  ## counts of the number of times attention has focussed (max) on these indices
    endcount_threshold = 1 ## number of times we require attention to focus on end before we consider synthesis finished
    t_ends = np.ones(ends.shape, dtype=int) * hp.max_T  ## The frame index when endcounts is sufficiently high, which we'll consider the end of the utterance
                                                        ## NB: initialised to max_T -- will default to this.

    t = start_clock('gen')
    for j in tqdm(range(hp.max_T)):
        if hp.multispeaker:
            _Y, _max_attentions, _alignments, = \
                sess.run([ g.Y, g.max_attentions, g.alignments],
                         {g.K: K,
                          g.V: V,
                          g.mels: Y,
                          g.speakers: speaker_data,
                          g.prev_max_attentions: prev_max_attentions}) ##
        else:
            _Y, _max_attentions, _alignments, = \
                sess.run([ g.Y, g.max_attentions, g.alignments],
                         {g.K: K,
                          g.V: V,
                          g.mels: Y,
                          g.prev_max_attentions: prev_max_attentions}) ## osw: removed global_step from synth loop
        Y[:, j, :] = _Y[:, j, :]
        prev_max_attentions = _max_attentions[:, j]

        ## Work out if we've reach end of any/all sentences in batch:-
        reached_end = (_max_attentions[:, j] >= ends) ## is attention focussing on or beyond end of textual sentence?
        endcounts += reached_end
        for (i,(current, endcount)) in enumerate(zip(t_ends, endcounts)):
            if current == hp.max_T: ## if hasn't changed from initialisation value
                if endcount >= endcount_threshold:
                    t_ends[i] = j
        ## Bail out early if all sentences seem to be finished:
        if (t_ends < hp.max_T).all():
            print('finished here:')
            print(t_ends)
            break

    return (Y, t_ends.tolist())

def encode_text(hp, L, g, sess, speaker_data=None):  ### TODO: remove speaker data?
    K, V = sess.run([ g.K, g.V], {g.L: L}) 
    return (K, V)

def get_text_lengths(L):
    ends = []  ## indices of first padding character after the last letter
    for i in range(len(L)):
        ends.append((np.where(L[i,:]==0)[0][0]))   ## TODO: have to go back to L to work this out?
    ends = np.array(ends)    
    return ends


def synth_mel2mag(hp, Y, g, sess, batchsize=0):
    #assert speaker_data==None  ## TODO: remove, or might speaker-condition SSRN at some point?
    
    if batchsize > 0:
        nbatches = len(Y) / batchsize
        batches = np.array_split(Y, nbatches)
    else:
        batches = [Y]

    Z = np.concatenate([sess.run(g.Z, {g.mels: Y_batch}) for Y_batch in batches])
    

    return Z

    


def split_batch(synth_batch, end_indices):
    outputs = []
    for i, predmel in enumerate(synth_batch):
        length = end_indices[i]
        outputs.append(predmel[:length, :])
        # print('Write %s'%(outdir + "/%s_mel%s.npy"%(name, speaker_id)))
        # np.save(outdir + "/%s_mel%s"%(name, speaker_id), predmel)
    return outputs

def make_mel_batch(hp, fnames, oracle=True):
    lengths = []
    if oracle:
        source = hp.coarse_audio_dir
        bases = [basename(fname) for fname in fnames]
        mels = [os.path.join(hp.coarse_audio_dir, base + '.npy') for base in bases]
    else:
        mels = fnames
    mels = [np.load(melfile) for melfile in mels] # [:1]  ## TODO
    #print (mels[0])
    #sys.exit('wvsrfbesrfb')
    mel_batch = np.zeros((len(mels), hp.max_T, hp.n_mels), np.float32)
    for (i,mel) in enumerate(mels):
        length,n = mel.shape
        mel_batch[i,:length,:] = mel
        lengths.append(length * hp.r)
    return mel_batch, lengths



def synthesize(hp, speaker_id='', num_sentences=0):
    assert hp.vocoder=='griffin_lim', 'Other vocoders than griffin_lim not yet supported'

    # Load data
    (fpaths, L) = load_data(hp, mode="synthesis")
    #L = L[:2,:]
    bases = [basename(fpath) for fpath in fpaths]

    if num_sentences > 0:
        assert num_sentences < len(bases)
        L = L[:num_sentences, :]

    if speaker_id:
        speaker2ix = dict(zip(hp.speaker_list, range(len(hp.speaker_list))))
        speaker_ix = speaker2ix[speaker_id]

        # speaker_data = np.zeros_like(L)
        # for i in range(len(L)):
        #     length = (np.where(L[i,:]==0)[0][0])
        #     speaker_data[i,:length] = speaker_ix

        ## Speaker codes are held in (batch, 1) matrix -- tiling is done in graph:
        speaker_data = np.ones((len(L), 1))  *  speaker_ix

    else:
        speaker_data = None

    # Load graph
    #g = Graph(hp,  mode="synthesize"); print("Graph 1 loaded")
    #g = Graph(hp, num=2, mode="synthesize"); print("Graph 2 loaded")
    ## map to appropriate type of graph depending on model_type
    g1 = Text2MelGraph(hp,  mode="synthesize"); print("Graph 1 loaded")
    g2 = SSRNGraph(hp,  mode="synthesize"); print("Graph 1 loaded")

    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())


        ### TODO: specify epoch from comm line?
        ### TODO: t2m and ssrn from separate configs


        # Restore parameters
        var_list = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, 'Text2Mel')
        saver1 = tf.train.Saver(var_list=var_list)
        savepath = hp.logdir + "-t2m"
        #print ([savepath])

        latest_checkpoint = tf.train.latest_checkpoint(savepath)
        #latest_checkpoint = '/disk/scratch/oliver/dc_tts_osw/work/lj_03/train-1/model_epoch_1000.000'

        #print('load from %s'%(latest_checkpoint)) 
        t2m_epoch = latest_checkpoint.strip('/ ').split('/')[-1].replace('model_epoch_', '')
        saver1.restore(sess, latest_checkpoint)
        print("Text2Mel Restored from latest epoch %s"%(t2m_epoch))

        var_list = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, 'SSRN') + \
                   tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, 'gs')
        saver2 = tf.train.Saver(var_list=var_list)
        savepath = hp.logdir + "-ssrn"        
        latest_checkpoint = tf.train.latest_checkpoint(savepath)
        # print('load from %s'%(latest_checkpoint))
        ssrn_epoch = latest_checkpoint.strip('/ ').split('/')[-1].replace('model_epoch_', '')
        saver2.restore(sess, latest_checkpoint)
        print("SSRN Restored from latest epoch %s"%(ssrn_epoch))




        t = start_clock('Text2Mel generating...')
        ### TODO: after futher efficiency testing, remove this fork
        if 1:  ### efficient route -- only make K&V once  ## 3.86, 3.70, 3.80 seconds (2 sentences)
            text_lengths = get_text_lengths(L)
            K, V = encode_text(hp, L, g1, sess, speaker_data=None)
            Y, lengths = synth_codedtext2mel(hp, K, V, text_lengths, g1, sess, speaker_data=speaker_data)
        else: ## 5.68, 5.43, 5.38 seconds (2 sentences)
            Y, lengths = synth_text2mel(hp, L, g1, sess, speaker_data=speaker_data)
        stop_clock(t)

        # print(Y[0,:,:])
        # print (np.isnan(Y).any())
        # print('nan1')



        t = start_clock('Mel2Mag generating...')
        Z = synth_mel2mag(hp, Y, g2, sess)
        stop_clock(t) 

        if (np.isnan(Z).any()):  ### TODO: keep?
            Z = np.nan_to_num(Z)

        # Generate wav files
        outdir = os.path.join(hp.sampledir, '%s_%s'%(t2m_epoch, ssrn_epoch))
        safe_makedir(outdir)
        for i, mag in enumerate(Z):
            print("Working on %s"%(bases[i]))
            mag = mag[:lengths[i]*hp.r,:]  ### trim to generated length
            
            if hp.vocoder=='magphase_compressed':
                mag = denorm(mag, s, hp.normtype)
                streams = split_streams(mag, ['mag', 'lf0', 'vuv', 'real', 'imag'], [60,1,1,45,45])
                wav = magphase_synth_from_compressed(streams, samplerate=hp.sr)
            elif hp.vocoder=='griffin_lim':                
                wav = spectrogram2wav(hp, mag)
            else:
                sys.exit('Unsupported vocoder type: %s'%(hp.vocoder))
            write(hp.sampledir + "/{}.wav".format(bases[i]), hp.sr, wav)








# ### before refactoring, 24/01/2018 TODO: clean up.
def synthesize_v1(hp, speaker_id='', num_sentences=0):
    assert hp.vocoder=='griffin_lim', 'Other vocoders than griffin_lim not yet supported'

    # Load data
    (fpaths, L) = load_data(hp, mode="synthesis")
    #L = L[:2,:]
    bases = [basename(fpath) for fpath in fpaths]

    if num_sentences > 0:
        assert num_sentences < len(bases)
        L = L[:num_sentences, :]

    if speaker_id:
        speaker2ix = dict(zip(hp.speaker_list, range(len(hp.speaker_list))))
        speaker_ix = speaker2ix[speaker_id]

        speaker_data = np.zeros_like(L)
        for i in range(len(L)):
            length = (np.where(L[i,:]==0)[0][0])
            speaker_data[i,:length] = speaker_ix

    # Load graph
    g = Graph(hp,  mode="synthesize"); print("Graph 1 loaded")
    #g = Graph(hp, num=2, mode="synthesize"); print("Graph 2 loaded")

    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())

        # Restore parameters
        var_list = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, 'Text2Mel')
        saver1 = tf.train.Saver(var_list=var_list)
        savepath = hp.logdir + "-1"
        print ([savepath])
        saver1.restore(sess, tf.train.latest_checkpoint(savepath))
        print("Text2Mel Restored!")

        var_list = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, 'SSRN') + \
                   tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, 'gs')
        saver2 = tf.train.Saver(var_list=var_list)
        savepath = hp.logdir + "-2"        
        saver2.restore(sess, tf.train.latest_checkpoint(savepath))
        print("SSRN Restored!")

        # Feed Forward
        ## mel
        Y = np.zeros((len(L), hp.max_T, hp.n_mels), np.float32)
        prev_max_attentions = np.zeros((len(L),), np.int32)

        t = start_clock('gen')
        for j in tqdm(range(hp.max_T)):
            if hp.multispeaker:
                _Y, _max_attentions, _alignments, = \
                    sess.run([ g.Y, g.max_attentions, g.alignments],
                             {g.L: L,
                              g.mels: Y,
                              g.speakers: speaker_data,
                              g.prev_max_attentions: prev_max_attentions}) ##
            else:
                _Y, _max_attentions, _alignments, = \
                    sess.run([ g.Y, g.max_attentions, g.alignments],
                             {g.L: L,
                              g.mels: Y,
                              g.prev_max_attentions: prev_max_attentions}) ## osw: removed global_step from synth loop
            Y[:, j, :] = _Y[:, j, :]
            prev_max_attentions = _max_attentions[:, j]
        stop_clock(t)


        print ('get mag...')
        # Get magnitude
        Z = sess.run(g.Z, {g.mels: Y}) # osw: Y -> mels

        # Generate wav files
        if not os.path.exists(hp.sampledir): os.makedirs(hp.sampledir)
        for i, mag in enumerate(Z):
            print("Working on file", i+1)
            if hp.vocoder=='magphase_compressed':
                mag = denorm(mag, s, hp.normtype)
                streams = split_streams(mag, ['mag', 'lf0', 'vuv', 'real', 'imag'], [60,1,1,45,45])
                wav = magphase_synth_from_compressed(streams, samplerate=hp.sr)
            elif hp.vocoder=='griffin_lim':
                wav = spectrogram2wav(hp, mag)
            else:
                sys.exit('evlsdvlsvsvbsfbv')
            write(hp.sampledir + "/{}.wav".format(bases[i]), hp.sr, wav)





def main_work():

    #################################################
      
    # ============= Process command line ============

    a = ArgumentParser()
    a.add_argument('-c', dest='config', required=True, type=str)
    a.add_argument('-speaker', default='', type=str)
    a.add_argument('-N', dest='num_sentences', default=0, type=int)
    
    opts = a.parse_args()
    
    # ===============================================
    
    # config = os.path.abspath(opts.config)
    # assert os.path.isfile(config)

    # conf_mod = imp.load_source('config', config)
    # hp = conf_mod.Hyperparams()

    hp = load_config(opts.config)

    if hp.multispeaker:
        assert opts.speaker, 'Please specify a speaker from speaker_list with -speaker flag'
        assert opts.speaker in hp.speaker_list

    synthesize(hp, speaker_id=opts.speaker, num_sentences=opts.num_sentences)


if __name__=="__main__":

    main_work()
